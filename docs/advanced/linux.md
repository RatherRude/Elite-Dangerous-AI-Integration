# Running on Linux

**WARNING: This setup is highly experimental and is potentially difficult, please contact us on discord**

We have a native Linux version available, but it requires some special setup. We will provide you with a download link in our discord server, and some instructions on how to get it running, here.

## Starting the application

1. Download the Linux version from the link we provide you in discord.
2. Extract the downloaded file to a folder of your choice, you may need to do this twice, as the zip file contains a `.tar.gz` file inside.
3. Open a terminal and navigate to the folder where you extracted the files.
4. Verify that you have the following files:

    - `bin/`

        - `covas-next-ui`

    - `lib/`

        - `covas-next-ui/`

            - `resources/`

                - `Chat`
                - `_internal/`

5. Start the application by running the `bin/covas-next-ui` executable.

    - Depending on your distribution, you may need to install additional dependencies, such as `libwebkit2gtk-4.1-0` or similar.

6. The application should now start and you should see the main menu.
7. Open the advanced settings tab and scroll to the `Linux Settings` section at the bottom.
8. Configure the following settings:

    ```
        ED AppData Path: "/home/<username>/.steam/steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/AppData/Local/Frontier Developments/Elite Dangerous/"
        ED Journal Path: "/home/<username>/.steam/steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous"
    ```
    Depending on your system, the paths may be different. The above paths are for a steam + proton installation of the game.

9. In the General Settings tab, setup your input and output audio devices, it is recommended to use the virtual pipewire or pulse devices.
10. Follow the regular [Getting Started](../index.md) guide to configure the rest of the application.
11. Start the AI and it should now work 🤞 If you have any issues, please contact us on discord.