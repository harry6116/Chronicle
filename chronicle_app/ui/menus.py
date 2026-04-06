import platform

import wx


class ChronicleMenuBar:
    def __init__(self, frame):
        self.frame = frame

    def install(self):
        menu_bar = wx.MenuBar()

        file_menu = wx.Menu()
        api_keys_id = wx.NewIdRef()
        help_open_id = wx.NewIdRef()
        help_about_build_id = wx.NewIdRef()
        donate_id = wx.NewIdRef()
        import_license_id = wx.NewIdRef()
        save_log_id = wx.NewIdRef()
        discover_scanners_id = wx.NewIdRef()
        scan_via_naps2_id = wx.NewIdRef()

        file_menu.Append(wx.ID_PREFERENCES, "&Preferences...\tAlt+P")
        file_menu.Append(api_keys_id, "API &Keys...\tAlt+K")
        file_menu.Append(import_license_id, "Import &License...")
        file_menu.Append(discover_scanners_id, "Find Connected &Devices...\tAlt+S")
        file_menu.Append(scan_via_naps2_id, "Scan via &NAPS2...\tAlt+N")
        file_menu.Append(save_log_id, "&Save Processing Log...\tAlt+L")

        mac_access_id = None
        if platform.system() == "Darwin":
            mac_access_id = wx.NewIdRef()
            file_menu.Append(mac_access_id, "Check Mac Folder &Access...\tAlt+M")

        menu_bar.Append(file_menu, "&File")

        help_menu = wx.Menu()
        help_menu.Append(help_open_id, "&Open User Guide\tF1")
        help_menu.Append(help_about_build_id, "&About Build...")
        help_menu.AppendSeparator()
        help_menu.Append(donate_id, "&Support Chronicle...")
        menu_bar.Append(help_menu, "&Help")

        self.frame.SetMenuBar(menu_bar)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnPrefs, id=wx.ID_PREFERENCES)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnApiKeys, id=api_keys_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnImportLicense, id=import_license_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnDiscoverScanners, id=discover_scanners_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnScanViaNaps2, id=scan_via_naps2_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnSaveLog, id=save_log_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnAppQuitRequested, id=wx.ID_EXIT)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnOpenHelp, id=help_open_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnAboutBuild, id=help_about_build_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnDonate, id=donate_id)

        if mac_access_id is not None:
            self.frame.Bind(wx.EVT_MENU, self.frame.OnMacAccessCheck, id=mac_access_id)

        return menu_bar
