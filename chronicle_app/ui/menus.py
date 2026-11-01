import platform

import wx

from chronicle_app.ui.bindings import bind_menu_action


class ChronicleMenuBar:
    def __init__(self, frame):
        self.frame = frame

    def install(self):
        menu_bar = wx.MenuBar()

        file_menu = wx.Menu()
        api_keys_id = wx.NewIdRef()
        help_open_id = wx.NewIdRef()
        help_manual_id = wx.NewIdRef()
        help_check_updates_id = wx.NewIdRef()
        help_version_history_id = wx.NewIdRef()
        help_about_build_id = wx.NewIdRef()
        donate_id = wx.NewIdRef()
        save_log_id = wx.NewIdRef()
        support_bundle_id = wx.NewIdRef()
        provider_matrix_id = wx.NewIdRef()
        private_offline_id = wx.NewIdRef()
        existing_ollama_id = wx.NewIdRef()
        resume_center_id = wx.NewIdRef()
        compare_outputs_id = wx.NewIdRef()
        recovery_workstation_id = wx.NewIdRef()

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
        file_menu.Append(recovery_workstation_id, "Recovery &Workbench Plan...")

        mac_access_id = None
        if platform.system() == "Darwin":
            mac_access_id = wx.NewIdRef()
            file_menu.Append(mac_access_id, "Check Mac Folder &Access...\tAlt+M")

        menu_bar.Append(file_menu, "&File")

        help_menu = wx.Menu()
        help_menu.Append(help_open_id, "Context &Help\tF1")
        help_menu.Append(help_manual_id, "&Open User Guide")
        help_menu.Append(help_check_updates_id, "Check for &Updates...\tShift+F1")
        help_menu.Append(help_version_history_id, "&Version History...")
        help_menu.Append(help_about_build_id, "&About Chronicle...")
        help_menu.AppendSeparator()
        help_menu.Append(donate_id, "&Support Chronicle...")
        menu_bar.Append(help_menu, "&Help")

        self.frame.SetMenuBar(menu_bar)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnPrefs, item_id=wx.ID_PREFERENCES, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnApiKeys, item_id=api_keys_id, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnSaveLog, item_id=save_log_id, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnPrivateOfflineMode, item_id=private_offline_id, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnUseExistingOllama, item_id=existing_ollama_id, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnExportSupportBundle, item_id=support_bundle_id, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnProviderCapabilityMatrix, item_id=provider_matrix_id, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnResumeCenter, item_id=resume_center_id, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnCompareOutputs, item_id=compare_outputs_id, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnRecoveryWorkbenchPlan, item_id=recovery_workstation_id, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnAppQuitRequested, item_id=wx.ID_EXIT, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnContextHelp, item_id=help_open_id, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnOpenHelp, item_id=help_manual_id, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnCheckForUpdates, item_id=help_check_updates_id, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnVersionHistory, item_id=help_version_history_id, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnAboutBuild, item_id=help_about_build_id, call_after=wx.CallAfter)
        bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnDonate, item_id=donate_id, call_after=wx.CallAfter)

        if mac_access_id is not None:
            bind_menu_action(self.frame, wx.EVT_MENU, self.frame.OnMacAccessCheck, item_id=mac_access_id, call_after=wx.CallAfter)

        return menu_bar
