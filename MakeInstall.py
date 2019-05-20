from Scripts import *
import os, sys, tempfile, shutil, zipfile, platform, json, time

class WinUSB:

    def __init__(self):
        self.u = utils.Utils("MakeInstall")
        self.min_plat = 9600
        # Make sure we're on windows
        self.verify_os()
        # Setup initial vars
        self.d = diskwin.Disk()
        self.dl = downloader.Downloader()
        self.r = run.Run()
        self.scripts = "Scripts"
        self.s_path  = os.path.join(os.path.dirname(os.path.realpath(__file__)), self.scripts)
        self.dd_url  = "http://www.chrysocome.net/downloads/ddrelease64.exe"
        self.dd_name = os.path.basename(self.dd_url)
        self.z_json = "https://sourceforge.net/projects/sevenzip/best_release.json"
        self.z_url2 = "https://www.7-zip.org/a/7z1806-x64.msi"
        self.z_url  = "https://www.7-zip.org/a/7z[[vers]]-x64.msi"
        self.z_name = "7z.exe"
        self.z_reg  = [
            {
                "loc" : "HKLM\\Software\\Classes\\CLSID\\{23170F69-40C1-278A-1000-000100020000}",
                "val" : "7-Zip Shell Extension"
            },
            {
                "loc" : "HKLM\\Software\\Classes\\CLSID\\{23170F69-40C1-278A-1000-000100020000}\InprocServer32",
                "name": "ThreadingModel",
                "val" : "Apartment"
            },
            {
                "loc" : "HKLM\\Software\\Classes\\*\\shellex\\ContextMenuHanders\\7-Zip",
                "val" : "{23170F69-40C1-278A-1000-000100020000}"
            },
            {
                "loc" : "HKLM\\Software\\Classes\\Directory\\shellex\\ContextMenuHanders\\7-Zip",
                "val" : "{23170F69-40C1-278A-1000-000100020000}"
            },
            {
                "loc" : "HKLM\\Software\\Classes\\Folder\\shellex\\ContextMenuHanders\\7-Zip",
                "val" : "{23170F69-40C1-278A-1000-000100020000}"
            },
        ]
        self.bi_url = "https://sites.google.com/site/gbrtools/home/software/bootice-portable/files/BOOTICE_v1.3.3.2.zip"
        self.bi_name = "BOOTICEx64.exe"
        self.clover_url = "https://api.github.com/repos/dids/clover-builder/releases/latest"
        # From Tim Sutton's brigadier:  https://github.com/timsutton/brigadier/blob/master/brigadier
        self.z_path = None
        self.z_path64 = os.path.join(os.environ['SYSTEMDRIVE'] + "\\", "Program Files", "7-Zip", "7z.exe")
        self.z_path32 = os.path.join(os.environ['SYSTEMDRIVE'] + "\\", "Program Files (x86)", "7-Zip", "7z.exe")
        self.recovery_suffixes = (
            "recoveryhdupdate.pkg",
            "recoveryhdmetadmg.pkg"
        )
        self.dd_bootsector = True
        self.boot0 = "boot0af"
        self.boot1 = "boot1f32alt"
        self.boot  = "boot6"
        self.efi_id = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b" # EFI
        self.bas_id = "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7" # Microsoft Basic Data
        self.hfs_id = "48465300-0000-11AA-AA11-00306543ECAC" # HFS+
        self.rec_id = "426F6F74-0000-11AA-AA11-00306543ECAC" # Apple Boot partition (Recovery HD)
    
    def verify_os(self):
        self.u.head("Verifying OS")
        print("")
        print("Verifying OS name...")
        if not os.name=="nt":
            print("")
            print("This script is only for Windows!")
            print("")
            self.u.grab("Press [enter] to exit...")
            exit(1)
        print(" - Name = NT")
        print("Verifying OS version...")
        # Verify we're at version 9600 or greater
        try:
            # Set plat to the last item of the output split by . - looks like:
            # Windows-8.1-6.3.9600
            # or this:
            # Windows-10-10.0.17134-SP0
            plat = int(platform.platform().split(".")[-1].split("-")[0])
        except:
            plat = 0
        if plat < self.min_plat:
            print("")
            print("Currently running {}, this script requires version {} or newer.".format(platform.platform(), self.min_plat))
            print("")
            self.u.grab("Press [enter] to exit...")
            exit(1)
        print(" - Version = {}".format(plat))
        print("")
        print("{} >= {}, continuing...".format(plat, self.min_plat))

    def get_disks_of_type(self, disk_list, disk_type=(0,2)):
        disks = {}
        for disk in disk_list:
            if disk_list[disk].get("type",0) in disk_type:
                disks[disk] = disk_list[disk]
        return disks

    def check_dd(self):
        # Checks if ddrelease64.exe exists in our Scripts dir
        # and if not - downloads it
        #
        # Returns True if exists/downloaded successfully
        # or False if issues.
        # Check for dd.exe in the current dir
        if os.path.exists(os.path.join(self.s_path, self.dd_name)):
            # print("Located {}!".format(self.dd_name))
            # Got it
            return True
        print("Couldn't locate {} - downloading...".format(self.dd_name))
        # Now we need to download
        self.dl.stream_to_file(self.dd_url, os.path.join(self.s_path, self.dd_name))
        print("")
        return os.path.exists(os.path.join(self.s_path, self.dd_name))

    def check_7z(self):
        # Check for 7z.exe in Program Files and if not - download the 7z msi and install
        #
        # Returns True if found, False if not
        if os.path.exists(self.z_path64):
            # Got it
            self.z_path = self.z_path64
            return True
        elif os.path.exists(self.z_path32):
            # Found the 32 bit version
            self.z_path = self.z_path32
            return True
        print("Didn't locate {} - downloading...".format(self.z_name))
        # Didn't find it - let's do some stupid stuff
        # First we get our json response - or rather, try to, then parse it
        # looking for the current version
        dl_url = None
        try:
            json = json.loads(self.dl.get_string(self.z_json))
            v_num = json.get("release",{}).get("filename","").split("/")[-1].lower().replace("7z","").replace(".exe","")
            if len(v_num):
                dl_url = self.url.replace("[[vers]]",v_num)
        except:
            pass
        if not dl_url:
            dl_url = self.z_url2
        temp = tempfile.mkdtemp()
        self.dl.stream_to_file(dl_url, os.path.join(temp, self.z_name))
        print("")
        print("Installing 7zip...")
        # From Tim Sutton's brigadier:  https://github.com/timsutton/brigadier/blob/master/brigadier
        self.r.run({"args":["msiexec", "/qn", "/i", os.path.join(temp, self.z_name)],"stream":True})
        print("Setting reg entries...")
        for x in self.z_reg:
            if not "val" in x or not "loc" in x:
                continue
            args = ["reg.exe","add",x["loc"]]
            if x.get("name",None):
                args.extend(["/v",x["name"]])
            if x.get("type",None):
                args.extend(["/t",x["type"]])
            if x.get("val",None):
                args.extend(["/d",x["val"]])
            args.append("/f")
            out = self.r.run({"args":args})
            if out[2] != 0:
                print("Error: {}".format(out[1]))
                print("")
                self.u.grab("Press [enter] to exit...")
        print("")
        return os.path.exists(self.z_path)

    def check_bi(self):
        # Checks for BOOTICEx64.exe in our scripts dir
        # and downloads it if need be
        if os.path.exists(os.path.join(self.s_path, self.bi_name)):
            # print("Located {}!".format(self.bi_name))
            # Got it
            return True
        print("Couldn't locate {} - downloading...".format(self.bi_name))
        temp = tempfile.mkdtemp()
        zfile = os.path.basename(self.bi_url)
        print("Downloading {}...".format(os.path.basename(self.bi_url)))
        self.dl.stream_to_file(self.bi_url, os.path.join(temp,zfile))
        print("")
        print(" - Extracting...")
        # Extract with built-in tools \o/
        os.chdir(temp)
        with zipfile.ZipFile(os.path.join(temp,zfile)) as z:
            z.extractall(temp)
        for x in os.listdir(temp):
            if self.bi_name.lower() in x.lower():
                # Found it
                print(" - Found {}".format(x))
                print("   - Copying to {} directory...".format(self.scripts))
                shutil.copy(os.path.join(temp,x), os.path.join(self.s_path,x))
        # Return the cd to the local script dir
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        # Remove the temp folder
        shutil.rmtree(temp,ignore_errors=True)
        return os.path.exists(os.path.join(self.s_path,self.bi_name))

    def get_dl_info(self):
        # Returns the latest download package and info in a
        # dictionary:  { "url" : dl_url, "name" : name, "info" : update_info }
        json_data = self.dl.get_string(self.clover_url, False)
        if not json_data or not len(json_data):
            return None
        try:
            j = json.loads(json_data)
        except:
            return None
        dl_link = next((x.get("browser_download_url", None) for x in j.get("assets", []) if x.get("browser_download_url", "").lower().endswith(".lzma")), None)
        if not dl_link:
            return None
        return { "url" : dl_link, "name" : os.path.basename(dl_link), "info" : j.get("body", None) }

    def get_size(self, size):
        # Returns the size passed as human readable
        if size == -1:
            return "Unknown"
        ext = ["B","KB","MB","GB","TB","PB"]
        s = float(size)
        s_dict = {}
        # Iterate the ext list, and divide by 1000 each time
        for e in ext:
            s_dict[e] = s
            s /= 1000
        # Get the maximum >= 1 type
        biggest = next((x for x in ext[::-1] if s_dict[x] >= 1), "B")
        # Round to 2 decimal places
        bval = round(s_dict[biggest], 2)
        # Strip any orphaned, trailing 0's
        non_zero = False
        z_list = []
        for z in str(bval).split(".")[1][::-1]:
            if z == "0" and not non_zero:
                # We have a zero - and haven't hit a non-zero yet
                continue
            # Either got a non-zero, or non_zero is already set
            non_zero = True # Set again - just in case
            z_list.append(z)
        if len(z_list):
            return "{}.{} {}".format(str(bval).split(".")[0], "".join(z_list[::-1]), biggest)
        else:
            return "{} {}".format(str(bval).split(".")[0], biggest)

    def diskpart_flag(self, disk, as_efi=False):
        # Sets and unsets the GUID needed for a GPT EFI partition ID
        self.u.head("Changing ID With DiskPart")
        print("")
        print("Setting type as {}...".format("EFI" if as_efi else "Basic Data"))
        print("")
        # - EFI system partition: c12a7328-f81f-11d2-ba4b-00a0c93ec93b
        # - Basic data partition: ebd0a0a2-b9e5-4433-87c0-68b6b72699c7
        dp_script = "\n".join([
            "select disk {}".format(disk.get("index",-1)),
            "sel part 1",
            "set id={}".format(self.efi_id if as_efi else self.bas_id)
        ])
        temp = tempfile.mkdtemp()
        script = os.path.join(temp, "diskpart.txt")
        try:
            with open(script,"w") as f:
                f.write(dp_script)
        except:
            shutil.rmtree(temp)
            print("Error creating script!")
            print("")
            self.u.grab("Press [enter] to return...")
            return
        # Let's try to run it!
        out = self.r.run({"args":["diskpart","/s",script],"stream":True})
        # Ditch our script regardless of whether diskpart worked or not
        shutil.rmtree(temp)
        print("")
        if out[2] != 0:
            # Error city!
            print("DiskPart exited with non-zero status ({}).  Aborting.".format(out[2]))
        else:
            print("Done - You may need to replug your drive for the")
            print("changes to take effect.")
        print("")
        self.u.grab("Press [enter] to return...")

    def diskpart_erase(self, disk, gpt=False):
        # Generate a script that we can pipe to diskpart to erase our disk
        self.u.head("Erasing With DiskPart")
        print("")
        # Then we'll re-gather our disk info on success and move forward
        # Using MBR to effectively set the individual partition types
        # Keeps us from having issues mounting the EFI on Windows -
        # and also lets us explicitly set the partition id for the main
        # data partition.
        if not gpt:
            print("Using MBR...")
            dp_script = "\n".join([
                "select disk {}".format(disk.get("index",-1)),
                "clean",
                "convert mbr",
                "create partition primary size=200",
                "format quick fs=fat32 label='CLOVER'",
                "active",
                "create partition primary id=AB" # AF = HFS, AB = Recovery
            ])
        else:
            print("Using GPT...")
            dp_script = "\n".join([
                "select disk {}".format(disk.get("index",-1)),
                "clean",
                "convert gpt",
                "create partition primary size=200",
                "format quick fs=fat32 label='CLOVER'",
                "create partition primary id={}".format(self.hfs_id)
            ])
        temp = tempfile.mkdtemp()
        script = os.path.join(temp, "diskpart.txt")
        try:
            with open(script,"w") as f:
                f.write(dp_script)
        except:
            shutil.rmtree(temp)
            print("Error creating script!")
            print("")
            self.u.grab("Press [enter] to return...")
            return
        # Let's try to run it!
        out = self.r.run({"args":["diskpart","/s",script],"stream":True})
        # Ditch our script regardless of whether diskpart worked or not
        shutil.rmtree(temp)
        if out[2] != 0:
            # Error city!
            print("")
            print("DiskPart exited with non-zero status ({}).  Aborting.".format(out[2]))
            print("")
            self.u.grab("Press [enter] to return...")
            return
        # We should now have a fresh drive to work with
        # Let's write an image or something
        self.u.head("Updating Disk Information")
        print("")
        print("Re-populating list...")
        self.d.update()
        print("Relocating disk {}".format(disk["index"]))
        disk = self.d.disks[str(disk["index"])]
        self.select_package(disk)

    def select_package(self, disk):
        self.u.head("Select Recovery Package")
        print("")
        print("{}. {} - {} ({})".format(
            disk.get("index",-1), 
            disk.get("model","Unknown"), 
            self.get_size(disk.get("size",-1)),
            ["Unknown","No Root Dir","Removable","Local","Network","Disc","RAM Disk"][disk.get("type",0)]
            ))
        print("")
        print("M. Main Menu")
        print("Q. Quit")
        print("")
        menu = self.u.grab("Please paste the recovery update pkg path to extract:  ")
        if menu.lower() == "q":
            self.u.custom_quit()
        if menu.lower() == "m":
            return
        path = self.u.check_path(menu)
        if not path:
            self.select_package(disk)
            return
        # Got the package - let's make sure it's named right - just in case
        if os.path.basename(path).lower().endswith(".hfs"):
            # We have an hfs image already - bypass extraction
            self.dd_image(disk, path)
            return
        # If it's a directory, find the first recovery hit
        if os.path.isdir(path):
            for f in os.listdir(path):
                if f.lower().endswith(self.recovery_suffixes):
                    path = os.path.join(path, f)
                    break
        # Make sure it's named right for recovery stuffs
        if not path.lower().endswith(self.recovery_suffixes):
            self.u.head("Invalid Package")
            print("")
            print("{} is not in the available recovery package names:\n{}".format(os.path.basename(path), ", ".join(self.recovery_suffixes)))
            print("")
            print("Ensure you're passing a proper recovery package.")
            print("")
            self.u.grab("Press [enter] to return to package selection...")
            self.select_package(disk)
            return
        self.u.head("Extracting Package")
        print("")
        temp = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(temp)
        # Extract in sections and remove any files we run into
        print("Extracting Recovery dmg...")
        out = self.r.run({"args":[self.z_path, "e", "-txar", path, "*.dmg"]})
        if out[2] != 0:
            shutil.rmtree(temp,ignore_errors=True)
            print("An error occurred extracting: {}".format(out[2]))
            print("")
            self.u.grab("Press [enter] to return...")
            return
        print("Extracting BaseSystem.dmg...")
        # No files to delete here - let's extract the next part
        out = self.r.run({"args":[self.z_path, "e", "*.dmg", "*/Base*.dmg"]})
        if out[2] != 0:
            shutil.rmtree(temp,ignore_errors=True)
            print("An error occurred extracting: {}".format(out[2]))
            print("")
            self.u.grab("Press [enter] to return...")
            return
        # If we got here - we should delete everything in the temp folder except
        # for a .dmg that starts with Base
        del_list = [x for x in os.listdir(temp) if not (x.lower().startswith("base") and x.lower().endswith(".dmg"))]
        for d in del_list:
            os.remove(os.path.join(temp, d))
        # Onto the last command
        print("Extracting hfs...")
        out = self.r.run({"args":[self.z_path, "e", "-tdmg", "Base*.dmg", "*.hfs"]})
        if out[2] != 0:
            shutil.rmtree(temp,ignore_errors=True)
            print("An error occurred extracting: {}".format(out[2]))
            print("")
            self.u.grab("Press [enter] to return...")
            return
        # If we got here - we should delete everything in the temp folder except
        # for a .dmg that starts with Base
        del_list = [x for x in os.listdir(temp) if not x.lower().endswith(".hfs")]
        for d in del_list:
            os.remove(os.path.join(temp, d))
        print("Extracted successfully!")
        hfs = next((x for x in os.listdir(temp) if x.lower().endswith(".hfs")),None)
        # Now to dd our image - if it exists
        if not hfs:
            print("Missing the .hfs file!  Aborting.")
            print("")
            self.u.grab("Press [enter] to return...")
        else:
            self.dd_image(disk, os.path.join(temp, hfs))
        shutil.rmtree(temp,ignore_errors=True)

    def dd_image(self, disk, image):
        # Let's dd the shit out of our disk
        self.u.head("Copying Image To Drive")
        print("")
        print("Image: {}".format(image))
        print("")
        print("Disk {}. {} - {} ({})".format(
            disk.get("index",-1), 
            disk.get("model","Unknown"), 
            self.get_size(disk.get("size",-1)),
            ["Unknown","No Root Dir","Removable","Local","Network","Disc","RAM Disk"][disk.get("type",0)]
            ))
        print("")
        args = [
            os.path.join(self.s_path, self.dd_name),
            "if={}".format(image),
            "of=\\\\?\\Device\Harddisk{}\Partition2".format(disk.get("index",-1)),
            "bs=8M",
            "--progress"
        ]
        print(" ".join(args))
        print("")
        print("This may take some time!")
        print("")
        out = self.r.run({"args":args})
        if len(out[1].split("Error")) > 1:
            # We had some error text - dd, even when failing likes to give us a 0
            # status code.  It also sends a ton of text through stderr - so we comb
            # that for "Error" then split by that to skip the extra fluff and show only
            # the error.
            print("An error occurred:\n\n{}".format("Error"+out[1].split("Error")[1]))
            print("")
            self.u.grab("Press [enter] to return to the main menu...")
            return
        # Install Clover to the target drive
        self.install_clover(disk)

    def install_clover(self, disk):
        self.u.head("Installing Clover")
        print("")
        print("Gathering info...")
        c = self.get_dl_info()
        if c == None:
            print(" - Error communicating with github!")
            print("")
            self.u.grab("Press [enter] to return...")
            return
        print(" - Got {}".format(c.get("name","Unknown Version")))
        print("Downloading...")
        temp = tempfile.mkdtemp()
        os.chdir(temp)
        clover_lzma = c["name"]
        self.dl.stream_to_file(c["url"], os.path.join(temp, c["name"]))
        print("") # Empty space to clear the download progress
        if not os.path.exists(os.path.join(temp, c["name"])):
            print(" - Download failed.  Aborting...")
            print("")
            self.u.grab("Press [enter] to return...")
            return
        # Got a valid file in our temp dir
        print("Extracting {}...".format(clover_lzma))
        out = self.r.run({"args":[self.z_path, "e", os.path.join(temp,clover_lzma)]})
        if out[2] != 0:
            shutil.rmtree(temp,ignore_errors=True)
            print(" - An error occurred extracting: {}".format(out[2]))
            print("")
            self.u.grab("Press [enter] to return...")
            return
        # Should result in a .tar file
        clover_tar = next((x for x in os.listdir(temp) if x.lower().endswith(".tar")),None)
        if not clover_tar:
            print(" - No .tar archive found - aborting...")
            print("")
            self.u.grab("Press [enter] to return...")
            return
        # Got the .tar archive - get the .iso
        print("Extracting {}...".format(clover_tar))
        out = self.r.run({"args":[self.z_path, "e", os.path.join(temp,clover_tar)]})
        if out[2] != 0:
            shutil.rmtree(temp,ignore_errors=True)
            print(" - An error occurred extracting: {}".format(out[2]))
            print("")
            self.u.grab("Press [enter] to return...")
            return
        # Should result in a .iso file
        clover_iso = next((x for x in os.listdir(temp) if x.lower().endswith(".iso")),None)
        if not clover_tar:
            print(" - No .iso found - aborting...")
            print("")
            self.u.grab("Press [enter] to return...")
            return
        # Got the .iso - let's extract the needed parts
        print("Extracting EFI from {}...".format(clover_iso))
        out = self.r.run({"args":[self.z_path, "x", os.path.join(temp,clover_iso), "EFI*"]})
        if out[2] != 0:
            shutil.rmtree(temp,ignore_errors=True)
            print(" - An error occurred extracting: {}".format(out[2]))
            print("")
            self.u.grab("Press [enter] to return...")
            return
        print("Extracting {} from {}...".format(self.boot0,clover_iso))
        out = self.r.run({"args":[self.z_path, "e", os.path.join(temp,clover_iso), self.boot0, "-r"]})
        if out[2] != 0:
            shutil.rmtree(temp,ignore_errors=True)
            print(" - An error occurred extracting: {}".format(out[2]))
            print("")
            self.u.grab("Press [enter] to return...")
            return
        print("Extracting {} from {}...".format(self.boot1,clover_iso))
        out = self.r.run({"args":[self.z_path, "e", os.path.join(temp,clover_iso), self.boot1, "-r"]})
        if out[2] != 0:
            shutil.rmtree(temp,ignore_errors=True)
            print(" - An error occurred extracting: {}".format(out[2]))
            print("")
            self.u.grab("Press [enter] to return...")
            return
        print("Extracting {} from {}...".format(self.boot,clover_iso))
        out = self.r.run({"args":[self.z_path, "e", os.path.join(temp,clover_iso), self.boot, "-r"]})
        if out[2] != 0:
            shutil.rmtree(temp,ignore_errors=True)
            print(" - An error occurred extracting: {}".format(out[2]))
            print("")
            self.u.grab("Press [enter] to return...")
            return
        # At this point, we should have a boot0xx file and an EFI folder in the temp dir
        # We need to udpate the disk list though - to reflect the current file system on part 1
        # of our current disk
        self.d.update() # assumes our disk number stays the same
        part = self.d.disks[str(disk["index"])]["partitions"].get("0",{}).get("letter",None) # get the first partition's letter
        if part == None:
            shutil.rmtree(temp,ignore_errors=True)
            print("Lost original disk - or formatting failed!")
            print("")
            self.u.grab("Press [enter] to return...")
            return
        # Here we have our disk and partitions and such - the CLOVER partition
        # will be the first partition
        # Let's copy over the EFI folder and then dd the boot0xx file
        print("Copying EFI folder to {}/EFI...".format(part))
        if os.path.exists("{}/EFI".format(part)):
            print(" - EFI exists - removing...")
            shutil.rmtree("{}/EFI".format(part),ignore_errors=True)
            time.sleep(1) # Added because windows is dumb
        shutil.copytree(os.path.join(temp,"EFI"), "{}/EFI".format(part))
        # Copy boot6 over to the root of the EFI volume - and rename it to boot
        print("Copying {} to {}/boot...".format(self.boot,part))
        shutil.copy(os.path.join(temp,self.boot),"{}/boot".format(part))
        # Use bootice to update the MBR and PBR - always on the first
        # partition (which is 0 in bootice)
        print("Updating the MBR with {}...".format(self.boot0))
        args = [
            os.path.join(self.s_path,self.bi_name),
            "/device={}".format(disk.get("index",-1)),
            "/mbr",
            "/restore",
            "/file={}".format(os.path.join(temp,self.boot0)),
            "/keep_dpt",
            "/quiet"
        ]
        out = self.r.run({"args":args})
        if out[2] != 0:
            shutil.rmtree(temp,ignore_errors=True)
            print(" - An error occurred updating the MBR: {}".format(out[2]))
            print("")
            self.u.grab("Press [enter] to return...")
            return
        print("Updating the PBR with {}...".format(self.boot1))
        args = [
            os.path.join(self.s_path,self.bi_name),
            "/device={}:0".format(disk.get("index",-1)),
            "/pbr",
            "/restore",
            "/file={}".format(os.path.join(temp,self.boot1)),
            "/keep_bpb",
            "/quiet"
        ]
        out = self.r.run({"args":args})
        if out[2] != 0:
            shutil.rmtree(temp,ignore_errors=True)
            print(" - An error occurred updating the PBR: {}".format(out[2]))
            print("")
            self.u.grab("Press [enter] to return...")
            return
        print("Cleaning up...")
        shutil.rmtree(temp,ignore_errors=True)
        print("")
        print("Done.")
        print("")
        self.u.grab("Press [enter] to return to the main menu...")

    def main(self):
        # Start out with our cd in the right spot.
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        # Let's make sure we have the required files needed
        self.u.head("Checking Required Tools")
        print("")
        if not self.check_dd():
            print("Couldn't find or install {} - aborting!".format(self.dd_name))
            exit(1)
        if not self.check_7z():
            print("Couldn't find or install {} - aborting!".format(self.z_name))
            exit(1)
        if not self.check_bi():
            print("Couldn't find or install {} - aborting!".format(self.bi_name))
            exit(1)
        # Let's just setup a real simple interface and try to write some data
        self.u.head("Gathering Disk Info")
        print("")
        print("Populating list...")
        self.d.update()
        print("")
        print("Done!")
        # Let's serve up a list of *only* removable media
        self.u.head("Potential Removable Media")
        print("")
        rem_disks = self.get_disks_of_type(self.d.disks)

        # SHOWING ALL DISKS CURRENTLY - CHANGE THIS FOR RELEASE!!!!
        # rem_disks = self.d.disks

        # Types: 0 = Unknown, 1 = No Root Dir, 2 = Removable, 3 = Local, 4 = Network, 5 = Disc, 6 = RAM disk

        print("!WARNING!  This list includes both Removable AND")
        print("!WARNING!  Unknown disk types.  Be ABSOLUTELY sure")
        print("!WARNING!  before selecting a disk!")
        print("")
        for disk in sorted(rem_disks):
            print("{}. {} - {} ({})".format(
                disk, 
                rem_disks[disk].get("model","Unknown"), 
                self.get_size(rem_disks[disk].get("size",-1)),
                ["Unknown","No Root Dir","Removable","Local","Network","Disc","RAM Disk"][rem_disks[disk].get("type",0)]
                ))
            if not len(rem_disks[disk].get("partitions",{})):
                print("   No Mounted Partitions")
            else:
                parts = rem_disks[disk]["partitions"]
                for p in sorted(parts):
                    print("   {}. {} ({}) {} - {}".format(
                        p,
                        parts[p].get("letter","No Letter"),
                        "No Name" if not parts[p].get("name",None) else parts[p].get("name","No Name"),
                        parts[p].get("file system","Unknown FS"),
                        self.get_size(parts[p].get("size",-1))
                    ))
        print("")
        print("Q. Quit")
        print("")
        print("Usage: [drive][option (only one allowed)] (eg. 1C)")
        print("  Options are as follows with precedence C > E > U > G:")
        print("    C = Only install Clover to the drive's first partition.")
        print("    E = Sets the type of the drive's first partition to EFI.")
        print("    U = Similar to E, but sets the type to Basic Data (useful for editing).")
        print("    G = Format as GPT (default is MBR).")
        print("")
        menu = self.u.grab("Please select a disk or press [enter] with no options to refresh:  ")
        if not len(menu):
            self.main()
            return
        if menu.lower() == "q":
            self.u.custom_quit()
        only_clover = set_efi = unset_efi = use_gpt = False
        if "c" in menu.lower():
            only_clover = True
            menu = menu.lower().replace("c","")
        if "e" in menu.lower():
            set_efi = True
            menu = menu.lower().replace("e","")
        if "u" in menu.lower():
            unset_efi = True
            menu = menu.lower().replace("u","")
        if "g" in menu.lower():
            use_gpt = True
            menu = menu.lower().replace("g","")

        selected_disk = rem_disks.get(menu,None)
        if not selected_disk:
            self.u.head("Invalid Choice")
            print("")
            print("Disk {} is not an option.".format(menu))
            print("")
            self.u.grab("Returning in 5 seconds...", timeout=5)
            self.main()
            return
        # Got a disk!
        if only_clover:
            self.install_clover(selected_disk)
        elif set_efi:
            self.diskpart_flag(selected_disk, True)
        elif unset_efi:
            self.diskpart_flag(selected_disk, False)
        else:
            # Check erase
            while True:
                self.u.head("Erase {}".format(selected_disk.get("model","Unknown")))
                print("")
                print("{}. {} - {} ({})".format(
                    selected_disk.get("index",-1), 
                    selected_disk.get("model","Unknown"), 
                    self.get_size(selected_disk.get("size",-1)),
                    ["Unknown","No Root Dir","Removable","Local","Network","Disc","RAM Disk"][selected_disk.get("type",0)]
                    ))
                print("")
                print("If you continue - THIS DISK WILL BE ERASED")
                print("ALL DATA WILL BE LOST AND ALL PARTITIONS WILL")
                print("BE REMOVED!!!!!!!")
                print("")
                yn = self.u.grab("Continue? (y/n):  ")
                if yn.lower() == "n":
                    self.main()
                    return
                if yn.lower() == "y":
                    break
            # Got the OK to erase!  Let's format a diskpart script!
            self.diskpart_erase(selected_disk, use_gpt)
        self.main()

w = WinUSB()
w.main()
