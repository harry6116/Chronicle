import os
import time

import wx
import wx.adv as wxadv

from chronicle_app.config import MODEL_OVERRIDE_CHOICES, PROFILE_CHOICES, TRANSLATION_TARGETS


class FirstLaunchNoticeDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Before You Start", size=(700, 470))
        self.SetBackgroundColour(wx.Colour(248, 244, 233))

        root = wx.BoxSizer(wx.VERTICAL)

        banner = wx.Panel(self)
        banner.SetBackgroundColour(wx.Colour(18, 78, 102))
        banner_sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(banner, label="Chronicle Review Reminder")
        title.SetForegroundColour(wx.Colour(255, 248, 231))
        title_font = title.GetFont()
        title_font = title_font.Bold()
        title_font.PointSize += 4
        title.SetFont(title_font)
        banner_sizer.Add(title, 0, wx.ALL, 16)

        subtitle = wx.StaticText(
            banner,
            label="Chronicle is designed to support accessible reading and careful review, not replace human judgment.",
        )
        subtitle.SetForegroundColour(wx.Colour(222, 240, 245))
        subtitle.Wrap(620)
        banner_sizer.Add(subtitle, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 16)
        banner.SetSizer(banner_sizer)
        root.Add(banner, 0, wx.EXPAND)

        body = wx.Panel(self)
        body.SetBackgroundColour(wx.Colour(255, 251, 242))
        body_sizer = wx.BoxSizer(wx.VERTICAL)

        intro = wx.StaticText(
            body,
            label=(
                "Chronicle is an AI-assisted document-reading and review tool, not a substitute for "
                "professional review, certified transcription, or qualified advice."
            ),
        )
        intro.SetForegroundColour(wx.Colour(62, 45, 36))
        intro_font = intro.GetFont()
        intro_font = intro_font.Bold()
        intro_font.PointSize += 1
        intro.SetFont(intro_font)
        intro.Wrap(620)
        body_sizer.Add(intro, 0, wx.ALL, 16)

        guidance = wx.StaticText(
            body,
            label=(
                "Chronicle can make mistakes, miss details, or misread difficult layouts. For legal, medical, "
                "financial, compliance, evidentiary, or other high-risk use, verify results against the original "
                "source and use a qualified human reviewer where appropriate."
            ),
        )
        guidance.SetForegroundColour(wx.Colour(86, 64, 53))
        guidance.Wrap(620)
        body_sizer.Add(guidance, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 16)

        note_panel = wx.Panel(body)
        note_panel.SetBackgroundColour(wx.Colour(243, 226, 184))
        note_sizer = wx.BoxSizer(wx.HORIZONTAL)
        note = wx.StaticText(
            note_panel,
            label="By continuing, you acknowledge that Chronicle output may require human verification before use, filing, or sharing.",
        )
        note.SetForegroundColour(wx.Colour(92, 61, 0))
        note.Wrap(590)
        note_sizer.Add(note, 1, wx.ALL | wx.EXPAND, 12)
        note_panel.SetSizer(note_sizer)
        body_sizer.Add(note_panel, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 16)

        self.chk_dont_show_again = wx.CheckBox(body, label="Don't show again after I agree")
        self.chk_dont_show_again.SetValue(True)
        self.chk_dont_show_again.SetForegroundColour(wx.Colour(62, 45, 36))
        body_sizer.Add(self.chk_dont_show_again, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 16)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_exit = wx.Button(body, wx.ID_CANCEL, "Exit Chronicle")
        self.btn_exit.SetBackgroundColour(wx.Colour(120, 58, 58))
        self.btn_exit.SetForegroundColour(wx.Colour(255, 248, 231))

        self.btn_agree = wx.Button(body, wx.ID_OK, "I Agree")
        self.btn_agree.SetDefault()
        self.btn_agree.SetBackgroundColour(wx.Colour(34, 107, 62))
        self.btn_agree.SetForegroundColour(wx.Colour(255, 248, 231))

        buttons.Add(self.btn_exit, 0, wx.RIGHT, 10)
        buttons.AddStretchSpacer(1)
        buttons.Add(self.btn_agree, 0)
        body_sizer.Add(buttons, 0, wx.ALL | wx.EXPAND, 16)

        body.SetSizer(body_sizer)
        root.Add(body, 1, wx.EXPAND)

        self.SetSizer(root)
        self.CentreOnParent()

    def ShouldSuppressFuturePrompts(self):
        return bool(self.chk_dont_show_again.GetValue())


class ScanSettingsDialog(wx.Dialog):
    def __init__(self, parent, scanners, cfg, *, script_dir):
        super().__init__(parent, title="Scan via NAPS2 - Settings", size=(640, 340))
        self.scanners = scanners or []
        self.cfg = cfg
        self._script_dir = script_dir

        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(0, 2, 10, 10)
        grid.AddGrowableCol(1, 1)

        grid.Add(wx.StaticText(panel, label="Input Device:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.choice_device = wx.Choice(panel, choices=self._build_device_labels())
        default_idx = self._default_device_index()
        if self.choice_device.GetCount() > 0:
            self.choice_device.SetSelection(default_idx)
        grid.Add(self.choice_device, 1, wx.EXPAND)

        grid.Add(wx.StaticText(panel, label="Scan Preset:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.choice_preset = wx.Choice(panel, choices=[
            "Text (300 DPI)",
            "Archival (600 DPI)",
            "Draft (200 DPI)",
            "Custom",
        ])
        self.choice_preset.Bind(wx.EVT_CHOICE, self.OnPresetChanged)
        grid.Add(self.choice_preset, 1, wx.EXPAND)

        grid.Add(wx.StaticText(panel, label="DPI:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.txt_dpi = wx.TextCtrl(panel)
        grid.Add(self.txt_dpi, 1, wx.EXPAND)

        grid.Add(wx.StaticText(panel, label="Output Folder:"), 0, wx.ALIGN_CENTER_VERTICAL)
        folder_row = wx.BoxSizer(wx.HORIZONTAL)
        default_dir = self.cfg.get("scan_output_dir", os.path.join(self._script_dir, "Input_Scans")).strip() or os.path.join(self._script_dir, "Input_Scans")
        self.txt_folder = wx.TextCtrl(panel, value=default_dir)
        self.btn_folder = wx.Button(panel, label="Browse...")
        self.btn_folder.Bind(wx.EVT_BUTTON, self.OnBrowseFolder)
        folder_row.Add(self.txt_folder, 1, wx.RIGHT, 8)
        folder_row.Add(self.btn_folder, 0)
        grid.Add(folder_row, 1, wx.EXPAND)

        root.Add(grid, 1, wx.ALL | wx.EXPAND, 12)

        hint = wx.StaticText(
            panel,
            label=(
                "Chronicle imports the new scan files into the queue only. "
                "Run Start Extraction separately after reviewing the queued scan."
            ),
        )
        root.Add(hint, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        btns = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK)
        cancel_btn = wx.Button(panel, wx.ID_CANCEL)
        ok_btn.SetLabel("Start Scan")
        btns.AddButton(ok_btn)
        btns.AddButton(cancel_btn)
        btns.Realize()
        root.Add(btns, 0, wx.ALIGN_RIGHT | wx.ALL, 12)
        panel.SetSizer(root)

        self._init_preset_and_dpi()

    def _build_device_labels(self):
        labels = []
        for scanner in self.scanners:
            name = scanner.get("name", "Unknown device")
            source = scanner.get("source", "").strip()
            labels.append(f"{name} ({source})" if source else name)
        return labels

    def _default_device_index(self):
        preferred_name = self.cfg.get("scan_last_device", "").strip().lower()
        if not preferred_name:
            return 0
        for idx, scanner in enumerate(self.scanners):
            if scanner.get("name", "").strip().lower() == preferred_name:
                return idx
        return 0

    def _init_preset_and_dpi(self):
        saved_dpi = int(self.cfg.get("scan_dpi", 300) or 300)
        if saved_dpi == 300:
            self.choice_preset.SetSelection(0)
            self.txt_dpi.SetValue("300")
            self.txt_dpi.Enable(False)
        elif saved_dpi == 600:
            self.choice_preset.SetSelection(1)
            self.txt_dpi.SetValue("600")
            self.txt_dpi.Enable(False)
        elif saved_dpi == 200:
            self.choice_preset.SetSelection(2)
            self.txt_dpi.SetValue("200")
            self.txt_dpi.Enable(False)
        else:
            self.choice_preset.SetSelection(3)
            self.txt_dpi.SetValue(str(saved_dpi))
            self.txt_dpi.Enable(True)

    def OnPresetChanged(self, event):
        preset = self.choice_preset.GetStringSelection()
        if preset == "Text (300 DPI)":
            self.txt_dpi.SetValue("300")
            self.txt_dpi.Enable(False)
        elif preset == "Archival (600 DPI)":
            self.txt_dpi.SetValue("600")
            self.txt_dpi.Enable(False)
        elif preset == "Draft (200 DPI)":
            self.txt_dpi.SetValue("200")
            self.txt_dpi.Enable(False)
        else:
            self.txt_dpi.Enable(True)
            self.txt_dpi.SetFocus()
            self.txt_dpi.SetSelection(-1, -1)
        event.Skip()

    def OnBrowseFolder(self, event):
        default_dir = self.txt_folder.GetValue().strip() or os.path.join(self._script_dir, "Input_Scans")
        os.makedirs(default_dir, exist_ok=True)
        dlg = wx.DirDialog(
            self,
            "Select folder for scanned files",
            defaultPath=default_dir,
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        )
        if dlg.ShowModal() == wx.ID_OK:
            self.txt_folder.SetValue(dlg.GetPath())
        dlg.Destroy()
        event.Skip()

    def GetSettings(self):
        selected_idx = self.choice_device.GetSelection()
        if selected_idx < 0 or selected_idx >= len(self.scanners):
            raise ValueError("Please choose a scanner device.")

        dpi_text = self.txt_dpi.GetValue().strip()
        if not dpi_text.isdigit():
            raise ValueError("DPI must be a whole number.")
        dpi = int(dpi_text)
        if dpi < 75 or dpi > 1200:
            raise ValueError("DPI must be between 75 and 1200.")

        folder = self.txt_folder.GetValue().strip()
        if not folder:
            raise ValueError("Please choose an output folder.")
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as ex:
            raise ValueError(f"Could not create output folder: {ex}")

        scanner = self.scanners[selected_idx]
        preset_label = self.choice_preset.GetStringSelection() or "Custom"
        return {
            "scanner": scanner,
            "dpi": dpi,
            "output_dir": folder,
            "preset_label": preset_label,
            "extract_mode": "manual",
            "auto_start": False,
            "merge_before_queue": False,
            "merge_extract_output": False,
        }


class SessionRecoveryDialog(wx.Dialog):
    RESUME = wx.ID_HIGHEST + 501
    LOAD_PAUSED = wx.ID_HIGHEST + 502
    START_FRESH = wx.ID_HIGHEST + 503

    def __init__(self, parent):
        super().__init__(parent, title="Recover Previous Session", size=(560, 260))
        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        msg = wx.StaticText(
            panel,
            label=(
                "Chronicle found an unfinished extraction session.\n\n"
                "Choose how you want to continue:"
            ),
        )
        msg.SetName("Session Recovery Message")
        root.Add(msg, 0, wx.ALL, 12)

        row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_resume = wx.Button(panel, self.RESUME, "Resume Previous Task")
        self.btn_resume.SetName("Resume Previous Task")
        self.btn_load = wx.Button(panel, self.LOAD_PAUSED, "Load but Pause")
        self.btn_load.SetName("Load but Pause")
        self.btn_fresh = wx.Button(panel, self.START_FRESH, "Start Fresh")
        self.btn_fresh.SetName("Start Fresh")
        row.Add(self.btn_resume, 1, wx.ALL, 6)
        row.Add(self.btn_load, 1, wx.ALL, 6)
        row.Add(self.btn_fresh, 1, wx.ALL, 6)
        root.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(root)
        self.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(self.RESUME), self.btn_resume)
        self.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(self.LOAD_PAUSED), self.btn_load)
        self.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(self.START_FRESH), self.btn_fresh)
        self.btn_resume.SetFocus()


class CloseRunningDialog(wx.Dialog):
    KEEP_OPEN = wx.ID_HIGHEST + 511
    SAVE_EXIT = wx.ID_HIGHEST + 512
    DISCARD_EXIT = wx.ID_HIGHEST + 513

    def __init__(self, parent, active_count, *, is_running=True):
        title = "Task In Progress" if is_running else "Keep Saved Queue?"
        super().__init__(parent, title=title, size=(620, 260))
        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        task_label = "task" if active_count == 1 else "tasks"
        if is_running:
            message = (
                f"Chronicle still has {active_count} active {task_label}.\n\n"
                "Choose whether to keep working, save this run so you can resume it later, or close and discard the unfinished task list."
            )
        else:
            message = (
                f"Chronicle has {active_count} saved {task_label} in the queue, but nothing is running yet.\n\n"
                "Choose whether to keep the queue for next launch, or close and discard it."
            )
        msg = wx.StaticText(
            panel,
            label=message,
        )
        msg.SetName("Close Warning Message")
        root.Add(msg, 0, wx.ALL, 12)

        row = wx.BoxSizer(wx.HORIZONTAL)
        keep_label = "Keep Working" if is_running else "Keep Queue"
        save_label = "Save and Close" if is_running else "Close and Keep Queue"
        discard_label = "Close and Discard"
        self.btn_keep = wx.Button(panel, self.KEEP_OPEN, keep_label)
        self.btn_keep.SetName(keep_label)
        self.btn_exit = wx.Button(panel, self.SAVE_EXIT, save_label)
        self.btn_exit.SetName(save_label)
        self.btn_discard = wx.Button(panel, self.DISCARD_EXIT, discard_label)
        self.btn_discard.SetName(discard_label)
        row.Add(self.btn_keep, 1, wx.ALL, 6)
        row.Add(self.btn_exit, 1, wx.ALL, 6)
        row.Add(self.btn_discard, 1, wx.ALL, 6)
        root.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(root)
        self.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(self.KEEP_OPEN), self.btn_keep)
        self.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(self.SAVE_EXIT), self.btn_exit)
        self.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(self.DISCARD_EXIT), self.btn_discard)
        self.btn_keep.SetFocus()


class ScheduleExtractionDialog(wx.Dialog):
    CLEAR_SCHEDULE = wx.ID_HIGHEST + 521

    def __init__(self, parent, existing_ts=None):
        super().__init__(parent, title="Schedule Extraction", size=(520, 280))
        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        help_text = wx.StaticText(
            panel,
            label=(
                "Schedule when Chronicle should start extraction.\n"
                "Chronicle must remain open for the scheduled run to trigger."
            ),
        )
        help_text.SetName("Schedule Extraction Help")
        root.Add(help_text, 0, wx.ALL, 12)

        grid = wx.FlexGridSizer(0, 2, 10, 10)
        grid.AddGrowableCol(1, 1)
        grid.Add(wx.StaticText(panel, label="Date:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.date_picker = wxadv.DatePickerCtrl(panel, style=wxadv.DP_DROPDOWN | wxadv.DP_SHOWCENTURY)
        grid.Add(self.date_picker, 1, wx.EXPAND)
        grid.Add(wx.StaticText(panel, label="Time:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.time_picker = wxadv.TimePickerCtrl(panel)
        grid.Add(self.time_picker, 1, wx.EXPAND)
        root.Add(grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)

        tz_label = wx.StaticText(panel, label=f"Local timezone: {time.tzname[0] if time.tzname else 'Local'}")
        root.Add(tz_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        existing = self._normalize_ts(existing_ts)
        if existing is not None:
            self._set_controls_from_timestamp(existing)
        else:
            self._set_controls_from_timestamp(time.time() + 600)

        btns = wx.StdDialogButtonSizer()
        btn_schedule = wx.Button(panel, wx.ID_OK, "Schedule")
        btn_clear = wx.Button(panel, self.CLEAR_SCHEDULE, "Clear Schedule")
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        btns.AddButton(btn_schedule)
        btns.AddButton(btn_clear)
        btns.AddButton(btn_cancel)
        btns.Realize()
        root.Add(btns, 0, wx.ALIGN_RIGHT | wx.ALL, 12)
        panel.SetSizer(root)
        self.SetAffirmativeId(wx.ID_OK)

    def _normalize_ts(self, value):
        try:
            ts = float(value)
        except (TypeError, ValueError):
            return None
        return ts if ts > 0 else None

    def _set_controls_from_timestamp(self, ts):
        dt = wx.DateTime.FromTimeT(int(ts))
        if dt.IsValid():
            self.date_picker.SetValue(dt)
            self.time_picker.SetValue(dt)

    def GetScheduledTimestamp(self):
        date_value = self.date_picker.GetValue()
        time_value = self.time_picker.GetValue()
        if not date_value.IsValid() or not time_value.IsValid():
            raise ValueError("Choose a valid date and time.")
        date_iso = date_value.FormatISODate()
        time_iso = time_value.FormatISOTime()
        if not date_iso or not time_iso:
            raise ValueError("Choose a valid date and time.")
        parsed = time.strptime(f"{date_iso} {time_iso}", "%Y-%m-%d %H:%M:%S")
        return float(time.mktime(parsed))


class ApiKeyDialog(wx.Dialog):
    @staticmethod
    def _looks_like_gemini_key(value):
        key = str(value or "").strip()
        if not key:
            return True
        return key.startswith("AIza") and len(key) == 39

    def __init__(self, parent, *, initial_keys=None, save_keys=None):
        super().__init__(parent, title="Chronicle API Keys Vault", size=(500, 350))
        self.keys = dict(initial_keys or {"gemini": "", "claude": "", "openai": ""})
        self._save_keys = save_keys
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        header = wx.StaticText(panel, label="Secure Vault: API keys are stored locally on this machine.")
        header.SetName("Secure Vault Instructions")
        vbox.Add(header, flag=wx.ALL, border=10)

        self.grid = wx.FlexGridSizer(3, 2, 10, 10)
        self.grid.AddGrowableCol(1, 1)

        gemini_label = wx.StaticText(panel, label="Google Gemini Key:")
        self.tg = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        self.tg.SetName("Google Gemini API Key")
        self.tg.SetValue(self.keys.get("gemini", ""))
        self.grid.Add(gemini_label, flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.tg, proportion=1, flag=wx.EXPAND)

        anthropic_label = wx.StaticText(panel, label="Anthropic Claude Key:")
        self.tc = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        self.tc.SetName("Anthropic Claude API Key")
        self.tc.SetValue(self.keys.get("claude", ""))
        self.grid.Add(anthropic_label, flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.tc, proportion=1, flag=wx.EXPAND)

        openai_label = wx.StaticText(panel, label="OpenAI GPT Key:")
        self.to = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        self.to.SetName("OpenAI GPT API Key")
        self.to.SetValue(self.keys.get("openai", ""))
        self.grid.Add(openai_label, flag=wx.ALIGN_CENTER_VERTICAL)
        self.grid.Add(self.to, proportion=1, flag=wx.EXPAND)

        vbox.Add(self.grid, proportion=1, flag=wx.ALL | wx.EXPAND, border=10)

        self.chk = wx.CheckBox(panel, label="Show API keys")
        self.chk.SetName("Show API Keys")
        self.chk.SetToolTip("When enabled, API key characters are visible for verification.")
        self.chk.Bind(wx.EVT_CHECKBOX, self.OnToggle)
        vbox.Add(self.chk, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        btns = wx.StdDialogButtonSizer()
        bs = wx.Button(panel, wx.ID_SAVE)
        bc = wx.Button(panel, wx.ID_CANCEL)
        bs.SetName("Save API Keys")
        bc.SetName("Cancel")
        bs.Bind(wx.EVT_BUTTON, self.OnSave)
        btns.AddButton(bs)
        btns.AddButton(bc)
        btns.Realize()
        vbox.Add(btns, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        panel.SetSizer(vbox)

    def OnToggle(self, event):
        style = 0 if self.chk.GetValue() else wx.TE_PASSWORD
        for attr in ["tg", "tc", "to"]:
            txt = getattr(self, attr)
            val = txt.GetValue()
            name = txt.GetName()
            parent = txt.GetParent()
            replacement = wx.TextCtrl(parent, style=style)
            replacement.SetValue(val)
            replacement.SetName(name)
            replacement.SetToolTip(txt.GetToolTipText())
            self.grid.Replace(txt, replacement)
            txt.Destroy()
            setattr(self, attr, replacement)
        self.grid.Layout()
        self.Layout()

    def OnSave(self, event):
        gemini_key = self.tg.GetValue().strip()
        if not self._looks_like_gemini_key(gemini_key):
            wx.MessageBox(
                "The Google Gemini key does not look valid. Gemini keys usually start with 'AIza' and are 39 characters long.\n\nPlease check the key and try again.",
                "Invalid Gemini API Key",
                wx.OK | wx.ICON_WARNING,
            )
            self.tg.SetFocus()
            self.tg.SetSelection(-1, -1)
            return
        self.keys = {
            "gemini": gemini_key,
            "claude": self.tc.GetValue().strip(),
            "openai": self.to.GetValue().strip(),
        }
        if self._save_keys is not None:
            self._save_keys(self.keys)
        wx.MessageBox("API keys saved locally on this machine.", "Chronicle", wx.OK | wx.ICON_INFORMATION)
        self.EndModal(wx.ID_OK)


class PrefsDialog(wx.Dialog):
    def __init__(
        self,
        parent,
        cfg,
        *,
        config_file,
        save_json,
        get_translation_target,
        profile_tooltip_text,
        apply_profile_preset,
        license_status_text="",
        import_license_handler=None,
    ):
        super().__init__(parent, title="Chronicle Preferences", size=(640, 760))
        self.cfg = cfg
        self._config_file = config_file
        self._save_json = save_json
        self._get_translation_target = get_translation_target
        self._profile_tooltip_text = profile_tooltip_text
        self._apply_profile_preset = apply_profile_preset
        self._import_license_handler = import_license_handler

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        license_box = wx.StaticBox(panel, label="License Status")
        license_sizer = wx.StaticBoxSizer(license_box, wx.VERTICAL)
        self.tc_license_status = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.tc_license_status.SetMinSize((-1, 124))
        self.tc_license_status.SetValue(str(license_status_text or "License status unavailable"))
        self.tc_license_status.SetToolTip("Shows the currently installed Chronicle license status for this machine.")
        license_sizer.Add(self.tc_license_status, 1, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 8)
        license_hint = wx.StaticText(
            panel,
            label="Use Import License to install a signed offline Chronicle license file on this machine.",
        )
        license_sizer.Add(license_hint, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        self.btn_import_license = wx.Button(panel, label="Import License...")
        self.btn_import_license.Bind(wx.EVT_BUTTON, self.OnImportLicenseRequested)
        license_sizer.Add(self.btn_import_license, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 8)
        vbox.Add(license_sizer, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)

        vbox.Add(wx.StaticText(panel, label="Document Profile:"), flag=wx.LEFT | wx.TOP, border=10)
        self.dp = wx.Choice(panel, choices=[label for _, label in PROFILE_CHOICES])
        selected_profile = cfg.get("doc_profile", "standard")
        self.dp.SetToolTip(profile_tooltip_text(selected_profile))
        self.dp.Bind(wx.EVT_CHOICE, self.OnProfileChanged)
        vbox.Add(self.dp, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        vbox.Add(wx.StaticText(panel, label="Engine Override:"), flag=wx.LEFT | wx.TOP, border=10)
        self.model_override_choices = list(MODEL_OVERRIDE_CHOICES)
        self.mo = wx.Choice(panel, choices=[label for _, label in self.model_override_choices])
        self.mo.SetToolTip(
            "Optional. Automatic follows the document preset. A specific engine forces that provider when available."
        )
        vbox.Add(self.mo, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        vbox.Add(wx.StaticText(panel, label="Language Translation:"), flag=wx.LEFT | wx.TOP, border=10)
        self.ct = wx.Choice(
            panel,
            choices=[
                "Disable translation (keep original language)",
                "Keep original + add translation in brackets",
                "Translate only",
            ],
        )
        self.ct.Bind(wx.EVT_CHOICE, self.OnTranslationModeChanged)
        self.ct.SetToolTip("Choose translation behavior for non-English text.")
        vbox.Add(self.ct, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)
        vbox.Add(wx.StaticText(panel, label="Translation Target Language:"), flag=wx.LEFT | wx.TOP, border=10)
        self.tgt = wx.Choice(panel, choices=[name for name, _ in TRANSLATION_TARGETS])
        self.tgt.SetToolTip("Target language used when translation is enabled.")
        vbox.Add(self.tgt, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        vbox.Add(wx.StaticText(panel, label="Legacy Punctuation Mode:"), flag=wx.LEFT | wx.TOP, border=10)
        self.cp = wx.Choice(panel, choices=["Keep old-style punctuation as-is", "Normalize old-style punctuation"])
        self.cp.SetToolTip("Applies to legacy/archival punctuation handling only. Normalize can convert long-s and archaic punctuation patterns.")
        vbox.Add(self.cp, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        vbox.Add(wx.StaticText(panel, label="Historical Units/Currency:"), flag=wx.LEFT | wx.TOP, border=10)
        self.cu = wx.Choice(panel, choices=["Keep original only", "Keep original + add modern equivalence in brackets"])
        self.cu.SetToolTip("Examples: '16 shillings and eight [0.83 pounds]', '2 chains [40.23 m]'.")
        vbox.Add(self.cu, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        vbox.Add(wx.StaticText(panel, label="Abbreviation Handling:"), flag=wx.LEFT | wx.TOP, border=10)
        self.ca = wx.Choice(panel, choices=["Keep abbreviations as-is", "Expand abbreviations in brackets"])
        self.ca.SetToolTip("Expands contextual abbreviations, e.g., Bn [Battalion].")
        vbox.Add(self.ca, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        vbox.Add(wx.StaticText(panel, label="Image Description Mode:"), flag=wx.LEFT | wx.TOP, border=10)
        self.ci = wx.Choice(panel, choices=["Enable detailed image descriptions", "Disable image descriptions"])
        self.ci.SetToolTip("Disable mode outputs image placeholders for screen reader flow.")
        vbox.Add(self.ci, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        vbox.Add(wx.StaticText(panel, label="Printed Page References:"), flag=wx.LEFT | wx.TOP, border=10)
        self.cpn = wx.Choice(panel, choices=["Off for screen-reader flow", "On for transcription/reference work"])
        self.cpn.SetToolTip("Enable this when you need visible printed book/page references kept as explicit output markers for transcription or citation work.")
        vbox.Add(self.cpn, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        vbox.Add(wx.StaticText(panel, label="PDF Display Mode:"), flag=wx.LEFT | wx.TOP, border=10)
        self.cl = wx.Choice(panel, choices=["Standard PDF output", "Large print PDF output (18pt high-contrast)"])
        self.cl.SetToolTip("Large print mode applies only to PDF output.")
        vbox.Add(self.cl, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        vbox.Add(wx.StaticText(panel, label="Merge Mode:"), flag=wx.LEFT | wx.TOP, border=10)
        self.cm = wx.Choice(panel, choices=["Keep files separate", "Merge output into one master file"])
        self.cm.SetToolTip("Merge combines all processed files into a single continuous output.")
        vbox.Add(self.cm, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        vbox.Add(wx.StaticText(panel, label="Academic Footnote Handling:"), flag=wx.LEFT | wx.TOP, border=10)
        self.cf = wx.Choice(
            panel,
            choices=[
                "Relocate footnotes to endnotes section",
                "Keep footnotes inline",
                "Strict original footnote placement",
            ],
        )
        self.cf.SetToolTip("Used by Academic mode for journal-style footnote behavior.")
        vbox.Add(self.cf, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        vbox.Add(wx.StaticText(panel, label="Academic Annotation Handling:"), flag=wx.LEFT | wx.TOP, border=10)
        self.can = wx.Choice(
            panel,
            choices=[
                "Keep annotations inline",
                "Move annotations to endnotes section",
                "Strict verbatim annotation preservation",
            ],
        )
        self.can.SetToolTip("Used by Academic mode for margin/editorial annotation behavior.")
        vbox.Add(self.can, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        vbox.Add(wx.StaticText(panel, label="Source File Deletion:"), flag=wx.LEFT | wx.TOP, border=10)
        self.cd = wx.Choice(panel, choices=["Keep source files", "Delete source files after successful conversion"])
        self.cd.SetToolTip("Deletion happens only after successful output write.")
        vbox.Add(self.cd, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        vbox.Add(wx.StaticText(panel, label="File Collision Mode:"), flag=wx.LEFT | wx.TOP, border=10)
        self.cc = wx.Choice(panel, choices=["Skip (Default)", "Overwrite", "Auto-Number"])
        self.cc.SetToolTip("How to handle files with identical names in the output directory.")
        vbox.Add(self.cc, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)

        adv_box = wx.StaticBox(panel, label="Advanced (Optional)")
        adv_sizer = wx.StaticBoxSizer(adv_box, wx.VERTICAL)
        adv_sizer.Add(
            wx.StaticText(panel, label="Custom Prompt Additions (appended to core rule-set):"),
            flag=wx.LEFT | wx.RIGHT | wx.TOP,
            border=8,
        )
        self.tc_custom_prompt = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        self.tc_custom_prompt.SetMinSize((-1, 96))
        self.tc_custom_prompt.SetToolTip("Optional advanced instructions appended to Chronicle's built-in prompt.")
        adv_sizer.Add(self.tc_custom_prompt, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

        adv_sizer.Add(
            wx.StaticText(panel, label="Custom Command/Rule Strings (one per line recommended):"),
            flag=wx.LEFT | wx.RIGHT,
            border=8,
        )
        self.tc_custom_commands = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        self.tc_custom_commands.SetMinSize((-1, 96))
        self.tc_custom_commands.SetToolTip("Optional strict command-style instructions for advanced extraction behavior.")
        adv_sizer.Add(self.tc_custom_commands, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
        self.chk_pdf_audit = wx.CheckBox(panel, label="Enable PDF text-layer omission audit")
        self.chk_pdf_audit.SetToolTip(
            "Post-pass audit compares PDF text layer with extracted output and appends recovered content when needed."
        )
        adv_sizer.Add(self.chk_pdf_audit, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.chk_page_confidence = wx.CheckBox(panel, label="Enable page confidence scoring")
        self.chk_page_confidence.SetToolTip("Logs per-page confidence estimates for PDF processing. Off by default.")
        adv_sizer.Add(self.chk_page_confidence, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.chk_low_memory = wx.CheckBox(panel, label="Enable low-memory mode")
        self.chk_low_memory.SetToolTip(
            "Reduces memory pressure by disabling some heavy features and skipping large PDF audit passes."
        )
        adv_sizer.Add(self.chk_low_memory, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.chk_memory_telemetry = wx.CheckBox(panel, label="Enable memory telemetry in processing log")
        self.chk_memory_telemetry.SetToolTip("Logs peak process memory (RSS) at task boundaries for stress diagnostics.")
        adv_sizer.Add(self.chk_memory_telemetry, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.chk_auto_save_log = wx.CheckBox(panel, label="Auto-save processing log after each run")
        self.chk_auto_save_log.SetToolTip(
            "Automatically writes the engine processing log to a timestamped text file in the output/source directory."
        )
        adv_sizer.Add(self.chk_auto_save_log, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        vbox.Add(adv_sizer, 1, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)

        tmap = {"none": 0, "both": 1, "english_only": 2}
        cmap = {"skip": 0, "overwrite": 1, "auto": 2}
        pmap = {key: i for i, (key, _) in enumerate(PROFILE_CHOICES)}
        model_override_map = {key: i for i, (key, _) in enumerate(self.model_override_choices)}
        self.dp.SetSelection(pmap.get(selected_profile, 0))
        self.mo.SetSelection(model_override_map.get(str(cfg.get("model_override", "") or ""), 0))
        self.ct.SetSelection(tmap.get(cfg.get("translate_mode", "none"), 0))
        self.cc.SetSelection(cmap.get(cfg.get("collision_mode", "skip"), 0))
        target_name, _ = self._get_translation_target(cfg)
        target_choices = [name for name, _ in TRANSLATION_TARGETS]
        self.tgt.SetSelection(target_choices.index(target_name) if target_name in target_choices else 0)
        self.cp.SetSelection(1 if cfg.get("modernize_punctuation", False) else 0)
        self.cu.SetSelection(1 if cfg.get("unit_conversion", False) else 0)
        self.ca.SetSelection(1 if cfg.get("abbrev_expansion", False) else 0)
        self.ci.SetSelection(0 if cfg.get("image_descriptions", True) else 1)
        self.cpn.SetSelection(1 if cfg.get("preserve_original_page_numbers", False) else 0)
        self.cl.SetSelection(1 if cfg.get("large_print", False) else 0)
        self.cm.SetSelection(1 if cfg.get("merge_files", False) else 0)
        f_map = {"endnotes": 0, "inline": 1, "strict": 2}
        a_map = {"inline": 0, "endnotes": 1, "strict": 2}
        self.cf.SetSelection(f_map.get(cfg.get("academic_footnote_mode", "endnotes"), 0))
        self.can.SetSelection(a_map.get(cfg.get("academic_annotation_mode", "inline"), 0))
        self.cd.SetSelection(1 if cfg.get("delete_source_on_success", False) else 0)
        self.tc_custom_prompt.SetValue(str(cfg.get("custom_prompt", "")))
        self.tc_custom_commands.SetValue(str(cfg.get("custom_commands", "")))
        self.chk_pdf_audit.SetValue(bool(cfg.get("pdf_textlayer_audit", True)))
        self.chk_page_confidence.SetValue(bool(cfg.get("page_confidence_scoring", False)))
        self.chk_low_memory.SetValue(bool(cfg.get("low_memory_mode", False)))
        self.chk_memory_telemetry.SetValue(bool(cfg.get("memory_telemetry", False)))
        self.chk_auto_save_log.SetValue(bool(cfg.get("auto_save_processing_log", False)))
        self.UpdateAcademicControlState()
        self.OnTranslationModeChanged()

        btns = wx.StdDialogButtonSizer()
        bs = wx.Button(panel, wx.ID_SAVE)
        bc = wx.Button(panel, wx.ID_CANCEL)
        bs.Bind(wx.EVT_BUTTON, self.OnSave)
        btns.AddButton(bs)
        btns.AddButton(bc)
        btns.Realize()
        vbox.Add(btns, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        panel.SetSizer(vbox)

    def OnImportLicenseRequested(self, event):
        if callable(self._import_license_handler):
            updated_text = self._import_license_handler()
            if updated_text:
                self.tc_license_status.SetValue(str(updated_text))
        if event:
            event.Skip()

    def OnSave(self, event):
        trev = {0: "none", 1: "both", 2: "english_only"}
        crev = {0: "skip", 1: "overwrite", 2: "auto"}
        frev = {0: "endnotes", 1: "inline", 2: "strict"}
        arev = {0: "inline", 1: "endnotes", 2: "strict"}
        prev = {i: key for i, (key, _) in enumerate(PROFILE_CHOICES)}
        selected_target = self.tgt.GetStringSelection().strip() or "English"
        selected_profile = prev.get(self.dp.GetSelection(), "standard")
        self.cfg.update(
            {
                "doc_profile": selected_profile,
                "model_override": self.model_override_choices[self.mo.GetSelection()][0],
                "translate_mode": trev.get(self.ct.GetSelection(), "none"),
                "translate_target": selected_target,
                "collision_mode": crev.get(self.cc.GetSelection(), "skip"),
                "modernize_punctuation": self.cp.GetSelection() == 1,
                "unit_conversion": self.cu.GetSelection() == 1,
                "abbrev_expansion": self.ca.GetSelection() == 1,
                "image_descriptions": self.ci.GetSelection() == 0,
                "preserve_original_page_numbers": self.cpn.GetSelection() == 1,
                "large_print": self.cl.GetSelection() == 1,
                "merge_files": self.cm.GetSelection() == 1,
                "academic_footnote_mode": frev.get(self.cf.GetSelection(), "endnotes"),
                "academic_annotation_mode": arev.get(self.can.GetSelection(), "inline"),
                "delete_source_on_success": self.cd.GetSelection() == 1,
                "custom_prompt": self.tc_custom_prompt.GetValue().strip(),
                "custom_commands": self.tc_custom_commands.GetValue().strip(),
                "pdf_textlayer_audit": self.chk_pdf_audit.GetValue(),
                "page_confidence_scoring": self.chk_page_confidence.GetValue(),
                "low_memory_mode": self.chk_low_memory.GetValue(),
                "memory_telemetry": self.chk_memory_telemetry.GetValue(),
                "auto_save_processing_log": self.chk_auto_save_log.GetValue(),
                "academic_mode": selected_profile == "academic",
            }
        )
        if self.cfg.get("low_memory_mode", False) and self.cfg.get("pdf_textlayer_audit", True):
            self.cfg["pdf_textlayer_audit"] = False
        self._save_json(self._config_file, self.cfg)
        self.EndModal(wx.ID_OK)

    def OnProfileChanged(self, event):
        key = PROFILE_CHOICES[self.dp.GetSelection()][0]
        preset = dict(self.cfg)
        self._apply_profile_preset(
            preset,
            key,
            selected_model_name=self.cfg.get("model_name", "gemini-2.5-flash"),
            keep_selected_model=True,
        )
        self.dp.SetToolTip(self._profile_tooltip_text(key))
        tmap_rev = {"none": 0, "both": 1, "english_only": 2}
        cmap_rev = {"skip": 0, "overwrite": 1, "auto": 2}
        self.ct.SetSelection(tmap_rev.get(preset.get("translate_mode", "none"), 0))
        target_name, _ = self._get_translation_target(preset)
        target_choices = [name for name, _ in TRANSLATION_TARGETS]
        self.tgt.SetSelection(target_choices.index(target_name) if target_name in target_choices else 0)
        self.cc.SetSelection(cmap_rev.get(preset.get("collision_mode", "skip"), 0))
        self.cp.SetSelection(1 if preset.get("modernize_punctuation", False) else 0)
        self.cu.SetSelection(1 if preset.get("unit_conversion", False) else 0)
        self.ca.SetSelection(1 if preset.get("abbrev_expansion", False) else 0)
        self.ci.SetSelection(0 if preset.get("image_descriptions", True) else 1)
        self.cpn.SetSelection(1 if preset.get("preserve_original_page_numbers", False) else 0)
        self.cl.SetSelection(1 if preset.get("large_print", False) else 0)
        self.cm.SetSelection(1 if preset.get("merge_files", False) else 0)
        self.UpdateAcademicControlState()
        self.OnTranslationModeChanged()
        if event:
            event.Skip()

    def OnTranslationModeChanged(self, event=None):
        mode = self.ct.GetSelection()
        self.tgt.Enable(mode in (1, 2))
        if event:
            event.Skip()

    def UpdateAcademicControlState(self):
        selected_profile = PROFILE_CHOICES[self.dp.GetSelection()][0]
        is_academic = selected_profile == "academic"
        self.cf.Enable(is_academic)
        self.can.Enable(is_academic)
