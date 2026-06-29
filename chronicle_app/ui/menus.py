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
        save_log_id = wx.NewIdRef()
        support_bundle_id = wx.NewIdRef()
        provider_matrix_id = wx.NewIdRef()
        private_offline_id = wx.NewIdRef()
        existing_ollama_id = wx.NewIdRef()
        resume_center_id = wx.NewIdRef()
        compare_outputs_id = wx.NewIdRef()

        file_menu.Append(wx.ID_PREFERENCES, "&Preferences...\tAlt+P")
        file_menu.Append(api_keys_id, "API &Keys...\tAlt+K")
        file_menu.Append(save_log_id, "&Save Processing Log...\tAlt+L")
        file_menu.AppendSeparator()
        file_menu.Append(private_offline_id, "Private &Offline Mode...\tAlt+O")
        file_menu.Append(existing_ollama_id, "Set Up Local &Ollama...")
        file_menu.Append(support_bundle_id, "Export Support &Bundle...")
        file_menu.Append(provider_matrix_id, "Provider Capability &Matrix...")
        file_menu.Append(resume_center_id, "Open &Resume Center...")
        file_menu.Append(compare_outputs_id, "Compare Two &Outputs...")

        mac_access_id = None
        if platform.system() == "Darwin":
            mac_access_id = wx.NewIdRef()
            file_menu.Append(mac_access_id, "Check Mac Folder &Access...\tAlt+M")

        menu_bar.Append(file_menu, "&File")

        help_menu = wx.Menu()
        help_menu.Append(help_open_id, "&Open User Guide\tF1")
        help_menu.Append(help_about_build_id, "&About Chronicle...")
        help_menu.AppendSeparator()
        help_menu.Append(donate_id, "&Support Chronicle...")
        menu_bar.Append(help_menu, "&Help")

        self.frame.SetMenuBar(menu_bar)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnPrefs, id=wx.ID_PREFERENCES)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnApiKeys, id=api_keys_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnSaveLog, id=save_log_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnPrivateOfflineMode, id=private_offline_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnUseExistingOllama, id=existing_ollama_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnExportSupportBundle, id=support_bundle_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnProviderCapabilityMatrix, id=provider_matrix_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnResumeCenter, id=resume_center_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnCompareOutputs, id=compare_outputs_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnAppQuitRequested, id=wx.ID_EXIT)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnOpenHelp, id=help_open_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnAboutBuild, id=help_about_build_id)
        self.frame.Bind(wx.EVT_MENU, self.frame.OnDonate, id=donate_id)

        if mac_access_id is not None:
            self.frame.Bind(wx.EVT_MENU, self.frame.OnMacAccessCheck, id=mac_access_id)

        return menu_bar
