# Chronicle Installation Guide

Welcome to the Chronicle installation guide. This document will walk you through setting up Chronicle on your system and keeping it up to date.

## Initial Setup

1. Clone the Chronicle repository to your local machine.
2. Ensure you have Python and Rust installed on your system.
3. For the initial setup, you can use the provided update scripts below to automatically install all required dependencies and build the necessary components.

## Keeping Chronicle Updated

You do not need to manually run `pip install` or re-download ZIP files when a new version of Chronicle is released. We have included automated scripts to handle the entire update process for you.

### macOS Users

To update the software and all dependencies on macOS, simply run the update script from your terminal within the Chronicle directory:

`./update_mac.sh`

*Note: If you receive a permission error, ensure the script is executable by running `chmod +x update_mac.sh` in your terminal first.*

### Windows Users

To update the software and all dependencies on Windows, locate and run the following batch file in the Chronicle directory:

`update_windows.bat`

This script will automatically pull the latest repository changes, update your Python requirements, and rebuild the necessary Rust components.