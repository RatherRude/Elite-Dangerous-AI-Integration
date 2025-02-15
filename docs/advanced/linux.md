# Running on Linux

**WARNING: This setup is highly experimental and is potentially difficult, please contact us on discord**

We have a native Linux version available, but it requires some special setup. We will provide you with a download link in our discord server, and some instructions on how to get it running, here.

## Starting the application

1. Download the Linux version from the link we provide you in discord.
2. Extract the downloaded file to a folder of your choice.
3. Open a terminal and navigate to the folder where you extracted the files.
4. Mark the required files as executable by running the following command:
   ```bash
   chmod +x start.sh
   chmod +x AIGUI/AIGUI
   chmod +x Chat/Chat
   ```
5. Start the application by running the following command:
   ```bash
    ./start.sh
    ```
6. The application should now start and you should see the main menu.
7. Close the application normally by closing the window.
8. Edit the `config.json` file:
    1. Open the `config.json` file in a text editor.
    2. Change the path to the game files:
    ```json
    {
        ...
        "ed_journal_path": "/home/<username>/.steam/steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous",
        "ed_appdata_path": "/home/<username>/.steam/steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/AppData/Local/Frontier Developments/Elite Dangerous/",
    }
    ```
    Depending on your system, the paths may be different.
    3. Save the file and close the text editor.
9. Start the application again.
10. Configure the application as needed, api keys, etc.
11. Start the AI and it should now work 🤞