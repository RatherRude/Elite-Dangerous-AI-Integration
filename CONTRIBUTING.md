# Contributing to Elite Dangerous AI Integration

Thank you for your interest in contributing! Here's how to set up your development environment.

## Prerequisites

- **Python 3.12**: Make sure you have Python 3.12 installed. You can download it from [python.org](https://www.python.org/downloads/).
- **Node.js**: For Angular and Electron development.

## Getting the Code

1. **Fork the repository**: Click the "Fork" button on the top right of the repository page to create your own copy.

2. **Clone your fork**: Use the following command to clone your fork to your local machine:

   ```bash
   git clone your-fork-url
   ```

3. **Navigate to the project directory**:

   ```bash
   cd elite-dangerous-ai-integration
   ```

4. **Add the original repository as a remote** (optional but recommended):

   ```bash
   git remote add upstream official-repo-url
   ```

5. **Fetch the latest changes** from the original repository:

   ```bash
   git fetch upstream
   ```

6. **Create a new branch** for your changes:

   ```bash
   git checkout -b your-feature-branch
   ```

## Backend Setup (Python)

1. **Install Python 3.12**:

   Ensure you have at least Python 3.12 installed and available in your PATH. You can check this by running:

   ```bash
   python --version
   ```

   If you see a version number starting with `3.12` or above, you're good to go.

2. **Create a Virtual Environment:**

   Navigate to the project root directory in your terminal and run:

   ```bash
   python -m venv .venv
   ```

   This creates a virtual environment named `.venv` in the project root.

3. **Activate the Virtual Environment:**

   - On **Linux/macOS**:
     ```bash
     source .venv/bin/activate
     ```
   - On **Windows (Command Prompt)**:
     ```bat
     .venv\Scripts\activate.bat
     ```
   - On **Windows (PowerShell)**:
     `powershell
.venv\Scripts\Activate.ps1
`
     You should see `(.venv)` at the beginning of your terminal prompt.

4. **Install Dependencies:**

   With the virtual environment activated, install the required Python packages:

   ```bash
   pip install -r requirements.txt
   ```

## Frontend Setup (UI)

2.  **Install Node.js Dependencies:**

    ```bash
    npm run install:ui
    npm run install:electron
    ```

    This installs the necessary packages for the UI and Electron development.

## Linux Flatpak Runtime Maintenance

`com.covasnext.ui.yml` pins the Freedesktop Platform/SDK and Electron BaseApp to
the stable `26.08` branch. Keep `runtime-version` and `base-version` aligned and
quoted as strings. The Linux CI workflow installs dependencies directly from this
manifest, so it does not need separate runtime version pins.

[Freedesktop runtime branches](https://docs.flatpak.org/en/latest/available-runtimes.html#freedesktop)
receive two years of support, not indefinite LTS support. Before the selected
branch reaches end-of-life, move both version fields to a supported stable branch
that also has a matching
[Electron BaseApp](https://github.com/flathub/org.electronjs.Electron2.BaseApp)
release. Flatpak manages the matching graphics extensions automatically.

After building the Linux application artifacts, run `npm run package:flatpak` on
Linux to build a bundle with the selected runtime. Existing installations must
install the rebuilt bundle to switch runtimes; `flatpak update` alone cannot
change the runtime required by an old application bundle.

## Running the Application in Development Mode

1.  **Run the Electron App in Development mode:**

    ```bash
    npm start
    ```

    This will build and launch the application with hot-reloading for the frontend. The Python backend is reloaded when stopping the AI Assistant, so start and stop the assistant to see changes, or manually reload the page using right-click > Reload.
