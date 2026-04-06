from PyInstaller.utils.hooks import collect_submodules, is_module_satisfies


if is_module_satisfies('pydantic >= 2.0.0'):
    hiddenimports = [
        name for name in collect_submodules('pydantic')
        if not name.startswith('pydantic.v1')
    ]
else:
    hiddenimports = collect_submodules('pydantic')
