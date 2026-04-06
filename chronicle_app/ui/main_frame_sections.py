import wx


def build_queue_action_section(panel, *, bind, set_button_icon):
    queue_actions_label = wx.StaticText(panel, label="Quick Actions")
    queue_actions_label.SetName("Queue Quick Actions Label")

    queue_actions = wx.BoxSizer(wx.HORIZONTAL)
    btn_add = wx.Button(panel, label='Add Files...')
    btn_add.SetName('Add Files')
    btn_add.SetToolTip('Open the standard file browser and add one or more files to the queue.')
    bind(btn_add, 'add_files')
    set_button_icon(btn_add, wx.ART_FILE_OPEN)
    queue_actions.Add(btn_add, 1, wx.ALL, 5)

    btn_add_folder = wx.Button(panel, label='Add Folder...')
    btn_add_folder.SetName('Add Folder')
    btn_add_folder.SetToolTip('Open the standard folder browser and add supported files from a folder to the queue.')
    bind(btn_add_folder, 'add_folder')
    set_button_icon(btn_add_folder, wx.ART_FOLDER_OPEN)
    queue_actions.Add(btn_add_folder, 1, wx.ALL, 5)

    queue_tools = wx.BoxSizer(wx.HORIZONTAL)
    btn_remove = wx.Button(panel, label='Remove Selected')
    btn_remove.SetName('Remove Selected Files')
    btn_remove.SetToolTip('Remove the selected files from the queue.')
    bind(btn_remove, 'remove_selected')
    set_button_icon(btn_remove, wx.ART_DELETE)
    queue_tools.Add(btn_remove, 0, wx.ALL, 5)

    btn_task_actions = wx.Button(panel, label='Task Actions...')
    btn_task_actions.SetName('Task Actions Menu')
    btn_task_actions.SetToolTip('Open actions for the selected queue items, including stop, pause, resume, delete, or open folder.')
    bind(btn_task_actions, 'task_actions')
    set_button_icon(btn_task_actions, wx.ART_LIST_VIEW)
    queue_tools.Add(btn_task_actions, 0, wx.ALL, 5)

    btn_select_all = wx.Button(panel, label='Select All')
    btn_select_all.SetName('Select All Queue Items')
    btn_select_all.SetToolTip('Select every item in the queue. Keyboard shortcut: Cmd/Ctrl+A.')
    bind(btn_select_all, 'select_all')
    queue_tools.Add(btn_select_all, 0, wx.ALL, 5)

    btn_deselect_all = wx.Button(panel, label='Deselect All')
    btn_deselect_all.SetName('Deselect All Queue Items')
    btn_deselect_all.SetToolTip('Clear the current queue selection. Keyboard shortcut: Escape.')
    bind(btn_deselect_all, 'deselect_all')
    queue_tools.Add(btn_deselect_all, 0, wx.ALL, 5)

    btn_clear = wx.Button(panel, label='Clear List')
    btn_clear.SetName('Clear File List')
    btn_clear.SetToolTip('Remove everything from the queue.')
    bind(btn_clear, 'clear_list')
    set_button_icon(btn_clear, wx.ART_DELETE)
    queue_tools.Add(btn_clear, 0, wx.ALL, 5)

    return {
        'queue_actions_label': queue_actions_label,
        'queue_actions': queue_actions,
        'queue_tools': queue_tools,
        'btn_add': btn_add,
        'btn_add_folder': btn_add_folder,
        'btn_remove': btn_remove,
        'btn_task_actions': btn_task_actions,
        'btn_select_all': btn_select_all,
        'btn_deselect_all': btn_deselect_all,
        'btn_clear': btn_clear,
    }


def build_settings_section(panel, *, cfg, profile_choices, get_pdf_page_items_fn, bind):
    run_settings_label = wx.StaticText(panel, label='Extraction Settings')
    run_settings_label.SetName('Extraction Settings Label')

    top = wx.FlexGridSizer(1, 4, 10, 10)
    top.AddGrowableCol(1, 1)
    top.AddGrowableCol(3, 1)
    top.Add(wx.StaticText(panel, label='Document Preset:'), 0, wx.ALIGN_CENTER_VERTICAL)
    choice_profile = wx.Choice(panel, choices=[label for _, label in profile_choices])
    choice_profile.SetName('Document Preset Picker')
    choice_profile.SetToolTip(
        'Choose the document type that best matches what you are reading. '
        'This should usually be your first choice, because it changes Chronicle’s default reading behaviour for the rest of the settings. '
        'The list is ordered from common/general presets first to more specialist presets later. '
        'Some presets, especially newspapers, archival material, academic pages, and long technical manuals, can be much slower.'
    )
    selected_profile = cfg.get('doc_profile', 'standard')
    profile_index = next((i for i, (k, _) in enumerate(profile_choices) if k == selected_profile), 0)
    choice_profile.SetSelection(profile_index)
    bind(choice_profile, 'profile_choice')
    top.Add(choice_profile, 1, wx.EXPAND)

    top.Add(wx.StaticText(panel, label='Output Format for Next Run:'), 0, wx.ALIGN_CENTER_VERTICAL)
    format_choice = wx.Choice(panel, choices=['HTML', 'TXT', 'DOCX', 'MD', 'PDF', 'JSON', 'CSV', 'EPUB'])
    format_choice.SetName('Output Format Selector')
    format_choice.SetToolTip(
        "Choose how Chronicle should save the reading result:\n"
        "- HTML/MD/TXT: easy-to-read text output\n"
        "- DOCX/PDF: familiar document-style output\n"
        "- JSON/CSV: structured export for analysis or workflows\n"
        "- EPUB: e-reader friendly book output"
    )
    fmt_selection = {'html': 0, 'txt': 1, 'docx': 2, 'md': 3, 'pdf': 4, 'json': 5, 'csv': 6, 'epub': 7}
    format_choice.SetSelection(fmt_selection.get(cfg.get('format_type', 'html'), 0))
    bind(format_choice, 'format_choice')
    top.Add(format_choice, 1, wx.EXPAND)

    apply_settings_row = wx.BoxSizer(wx.HORIZONTAL)
    btn_apply_settings = wx.Button(panel, label='Apply Current Settings To Selected')
    btn_apply_settings.SetName('Apply Current Settings')
    btn_apply_settings.SetToolTip(
        'Apply the current reading settings to the selected queue items. If nothing is selected, Chronicle applies them to all queued or paused items.'
    )
    bind(btn_apply_settings, 'apply_settings')
    apply_settings_row.Add(btn_apply_settings, 0, wx.ALL, 5)

    preflight_row = wx.BoxSizer(wx.HORIZONTAL)
    btn_run_preflight = wx.Button(panel, label='Run Preflight')
    btn_run_preflight.SetName('Run Document Preflight')
    btn_run_preflight.SetToolTip(
        'Inspect the selected queued file with the current settings and show Chronicle’s preflight decision before the run starts.'
    )
    bind(btn_run_preflight, 'run_preflight')
    preflight_row.Add(btn_run_preflight, 0, wx.ALL, 5)

    preflight_summary = wx.StaticText(
        panel,
        label='Preflight ready. Select a queued file and run preflight to see what Chronicle detects before extraction starts.',
    )
    preflight_summary.SetName('Document Preflight Summary')
    preflight_summary.SetToolTip(
        'Shows the latest preflight result, including whether Chronicle sees strong source text or a harder scan-heavy path.'
    )
    preflight_row.Add(preflight_summary, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

    runtime_opts = wx.FlexGridSizer(0, 4, 8, 8)
    runtime_opts.AddGrowableCol(1, 1)
    runtime_opts.AddGrowableCol(3, 1)

    runtime_opts.Add(wx.StaticText(panel, label='Translation:'), 0, wx.ALIGN_CENTER_VERTICAL)
    run_translate_choice = wx.Choice(panel, choices=['Disable translation', 'Keep original + bracketed translation', 'Translate only'])
    run_translate_choice.SetToolTip('Choose whether Chronicle should translate the selected items while reading.')
    runtime_opts.Add(run_translate_choice, 1, wx.EXPAND)

    runtime_opts.Add(wx.StaticText(panel, label='Punctuation:'), 0, wx.ALIGN_CENTER_VERTICAL)
    run_punct_choice = wx.Choice(panel, choices=['Strictly preserve original punctuation', 'Modernize legacy punctuation'])
    run_punct_choice.SetToolTip('Choose whether Chronicle should preserve original punctuation or modernize it.')
    runtime_opts.Add(run_punct_choice, 1, wx.EXPAND)

    runtime_opts.Add(wx.StaticText(panel, label='Units/Currency:'), 0, wx.ALIGN_CENTER_VERTICAL)
    run_units_choice = wx.Choice(panel, choices=['Keep original units only', 'Keep original + add modern equivalence'])
    run_units_choice.SetToolTip('Choose whether Chronicle should keep original units only or add modern equivalents.')
    runtime_opts.Add(run_units_choice, 1, wx.EXPAND)

    runtime_opts.Add(wx.StaticText(panel, label='Abbreviations:'), 0, wx.ALIGN_CENTER_VERTICAL)
    run_abbrev_choice = wx.Choice(panel, choices=['Keep abbreviations as-is', 'Expand abbreviations in brackets'])
    run_abbrev_choice.SetToolTip('Choose whether Chronicle should keep abbreviations as written or expand them in brackets.')
    runtime_opts.Add(run_abbrev_choice, 1, wx.EXPAND)

    runtime_opts.Add(wx.StaticText(panel, label='Image Descriptions:'), 0, wx.ALIGN_CENTER_VERTICAL)
    run_images_choice = wx.Choice(panel, choices=['Enable image descriptions', 'Disable image descriptions'])
    run_images_choice.SetToolTip('Choose whether Chronicle should describe images it finds.')
    runtime_opts.Add(run_images_choice, 1, wx.EXPAND)

    runtime_opts.Add(wx.StaticText(panel, label='Printed Page References:'), 0, wx.ALIGN_CENTER_VERTICAL)
    run_page_numbers_choice = wx.Choice(panel, choices=['Off for screen-reader flow', 'On for transcription/reference work'])
    run_page_numbers_choice.SetName('Printed Page References Mode')
    run_page_numbers_choice.SetToolTip(
        'Choose whether Chronicle should suppress standalone printed page numbers and folios for smoother reading, or preserve them as explicit transcription references in the output.'
    )
    run_page_numbers_choice.SetSelection(1 if bool(cfg.get('preserve_original_page_numbers', False)) else 0)
    runtime_opts.Add(run_page_numbers_choice, 1, wx.EXPAND)

    runtime_opts.Add(wx.StaticText(panel, label='Seamless Merge:'), 0, wx.ALIGN_CENTER_VERTICAL)
    run_merge_choice = wx.Choice(panel, choices=['Save each source as its own output', 'Merge selected sources into one continuous output'])
    run_merge_choice.SetName('Seamless Merge Mode')
    run_merge_choice.SetToolTip(
        'Choose whether Chronicle should save one output per source file or merge the queued sources into a single continuous reading result. '
        'Useful for page sequences, book scans, and many images that belong to one document.'
    )
    runtime_opts.Add(run_merge_choice, 1, wx.EXPAND)

    lbl_run_largeprint = wx.StaticText(panel, label='PDF Display:')
    runtime_opts.Add(lbl_run_largeprint, 0, wx.ALIGN_CENTER_VERTICAL)
    run_largeprint_choice = wx.Choice(panel, choices=['Standard PDF output', 'Large print PDF output'])
    run_largeprint_choice.SetToolTip('Choose standard or large-print PDF output.')
    runtime_opts.Add(run_largeprint_choice, 1, wx.EXPAND)

    lbl_pdf_pages = wx.StaticText(panel, label='PDF Pages:')
    runtime_opts.Add(lbl_pdf_pages, 0, wx.ALIGN_CENTER_VERTICAL)
    choice_pdf_pages = wx.Choice(panel, choices=get_pdf_page_items_fn(cfg.get('pdf_page_scope', '')))
    choice_pdf_pages.SetName('PDF Pages to Extract')
    choice_pdf_pages.SetHelpText(
        'Choose which PDF pages Chronicle should extract. Select Custom to enter page groups such as 7, 1-30, or 1-30 185-220.'
    )
    choice_pdf_pages.SetToolTip(
        'Choose which PDF pages Chronicle should extract. Select Custom to enter page groups such as 7, 1-30, or 1-30 185-220.'
    )
    bind(choice_pdf_pages, 'pdf_pages')
    runtime_opts.Add(choice_pdf_pages, 1, wx.EXPAND)

    run_merge_choice.SetSelection(1 if bool(cfg.get('merge_files', False)) else 0)

    for ctrl in (run_translate_choice, run_punct_choice, run_units_choice, run_abbrev_choice, run_images_choice, run_page_numbers_choice, run_merge_choice, run_largeprint_choice):
        bind(ctrl, 'run_option')

    opts = wx.FlexGridSizer(0, 4, 8, 8)
    opts.AddGrowableCol(1, 1)
    opts.AddGrowableCol(3, 1)

    opts.Add(wx.StaticText(panel, label='Folder Scanning:'), 0, wx.ALIGN_CENTER_VERTICAL)
    choice_recursive = wx.Choice(panel, choices=['Selected folder only', 'Include all nested subfolders'])
    choice_recursive.SetToolTip('Choose whether Add Folder should scan only the selected folder or include every nested subfolder beneath it.')
    choice_recursive.SetSelection(1 if bool(cfg.get('recursive_scan', False)) else 0)
    opts.Add(choice_recursive, 1, wx.EXPAND)

    opts.Add(wx.StaticText(panel, label='Save Output To:'), 0, wx.ALIGN_CENTER_VERTICAL)
    dest_choice = wx.Choice(panel, choices=['Same folder as source file', 'Custom output folder'])
    dest_choice.SetToolTip('Choose whether results should be saved beside each source file or in one custom folder.')
    dest_choice.SetSelection(1 if int(cfg.get('dest_mode', 0)) == 1 else 0)
    bind(dest_choice, 'dest_mode')
    opts.Add(dest_choice, 1, wx.EXPAND)

    opts.Add(wx.StaticText(panel, label='Custom Folder:'), 0, wx.ALIGN_CENTER_VERTICAL)
    txt_dest = wx.TextCtrl(panel, value=cfg.get('custom_dest', ''))
    opts.Add(txt_dest, 1, wx.EXPAND)
    btn_dest = wx.Button(panel, label='Browse...')
    bind(btn_dest, 'choose_dest')
    opts.Add(btn_dest, 0, wx.EXPAND)

    safety_opts = wx.BoxSizer(wx.HORIZONTAL)
    chk_preserve_structure = wx.CheckBox(panel, label='Preserve source folder structure for nested folder scans')
    chk_preserve_structure.SetName('Preserve Source Folder Structure')
    chk_preserve_structure.SetToolTip('When Add Folder includes nested subfolders and you save to a custom output folder, Chronicle mirrors that folder structure in the results.')
    chk_preserve_structure.SetValue(bool(cfg.get('preserve_source_structure', True)))
    bind(chk_preserve_structure, 'safety_option')
    safety_opts.Add(chk_preserve_structure, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

    chk_delete_originals = wx.CheckBox(panel, label='Delete originals after successful extraction')
    chk_delete_originals.SetName('Delete Originals After Success')
    chk_delete_originals.SetToolTip('Warning: after a successful run, Chronicle deletes each original source file, including files found in nested subfolders.')
    chk_delete_originals.SetValue(bool(cfg.get('delete_source_on_success', False)))
    bind(chk_delete_originals, 'safety_option')
    safety_opts.Add(chk_delete_originals, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

    run_actions = wx.BoxSizer(wx.HORIZONTAL)
    btn_start = wx.Button(panel, label='Start Reading', size=(-1, 42))
    btn_start.SetName('Start Reading')
    btn_start.SetToolTip('Start reading everything that is currently queued.')
    bind(btn_start, 'start')
    set_button_icon = None
    run_actions.Add(btn_start, 2, wx.RIGHT, 8)

    btn_schedule = wx.Button(panel, label='Schedule Reading...', size=(-1, 42))
    btn_schedule.SetName('Schedule Reading')
    btn_schedule.SetToolTip('Choose a date and time for Chronicle to start reading automatically.')
    bind(btn_schedule, 'schedule')
    run_actions.Add(btn_schedule, 2)

    return {
        'run_settings_label': run_settings_label,
        'top': top,
        'format_choice': format_choice,
        'apply_settings_row': apply_settings_row,
        'btn_apply_settings': btn_apply_settings,
        'runtime_opts': runtime_opts,
        'run_translate_choice': run_translate_choice,
        'run_punct_choice': run_punct_choice,
        'run_units_choice': run_units_choice,
        'run_abbrev_choice': run_abbrev_choice,
        'run_images_choice': run_images_choice,
        'run_page_numbers_choice': run_page_numbers_choice,
        'run_merge_choice': run_merge_choice,
        'lbl_run_largeprint': lbl_run_largeprint,
        'run_largeprint_choice': run_largeprint_choice,
        'lbl_pdf_pages': lbl_pdf_pages,
        'choice_pdf_pages': choice_pdf_pages,
        'opts': opts,
        'preflight_row': preflight_row,
        'btn_run_preflight': btn_run_preflight,
        'preflight_summary': preflight_summary,
        'choice_recursive': choice_recursive,
        'dest_choice': dest_choice,
        'txt_dest': txt_dest,
        'btn_dest': btn_dest,
        'choice_profile': choice_profile,
        'safety_opts': safety_opts,
        'chk_preserve_structure': chk_preserve_structure,
        'chk_delete_originals': chk_delete_originals,
        'run_actions': run_actions,
        'btn_start': btn_start,
        'btn_schedule': btn_schedule,
    }


def build_progress_section(panel):
    progress_box = wx.StaticBoxSizer(wx.VERTICAL, panel, "Task Progress")
    progress_gauge = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
    progress_gauge.SetName("Task Progress Gauge")
    progress_gauge.SetToolTip("Shows overall progress for the current queue.")
    progress_box.Add(progress_gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

    progress_summary = wx.TextCtrl(panel, style=wx.TE_READONLY)
    progress_summary.SetName("Task Progress Summary")
    progress_summary.SetToolTip(
        "A text summary of queue progress, including what is running and what is finished."
    )
    progress_box.Add(progress_summary, 0, wx.EXPAND | wx.ALL, 8)
    return progress_box, progress_gauge, progress_summary


def build_log_section(panel, *, save_log_handler):
    log_label = wx.StaticText(panel, label='Processing Log (engine output only):')
    log_label.SetName('Processing Log Label')

    log_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
    log_ctrl.SetName('Processing Log Window')
    log_ctrl.SetToolTip('Shows the reading log, including progress updates and engine messages.')
    log_ctrl.SetMinSize((-1, 180))

    log_actions = wx.BoxSizer(wx.HORIZONTAL)
    save_button = wx.Button(panel, label='Save Log...')
    save_button.SetName('Save Processing Log')
    save_button.SetToolTip('Save the current reading log to a text file.')
    save_button.Bind(wx.EVT_BUTTON, save_log_handler)
    log_actions.Add(save_button, 0, wx.RIGHT, 8)
    return log_label, log_ctrl, log_actions, save_button
