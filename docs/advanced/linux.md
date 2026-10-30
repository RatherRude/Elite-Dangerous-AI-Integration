# Running on Linux

!!! danger

        WARNING: This setup is highly experimental and is potentially difficult, please contact us on discord


We have a native Linux version available, but it requires some special setup. Starting with version 2.6.0, we provide a flatpak package for easier installation, but it is still experimental and may not work on all distributions. If you encounter any issues, please contact us on discord.

## Starting the application

1. Ensure you have [Flatpak](https://flatpak.org/setup/) installed on your system. You can check if Flatpak is installed by running:

    ```bash
    flatpak --version
    ```

   If it is not installed, follow the instructions on the Flatpak website to install it.

2. Download the flatpak file from out latest release at [GitHub](https://github.com/RatherRude/Elite-Dangerous-AI-Integration/releases) (or contact us on discord if it is not available).

3. Open a terminal and navigate to the directory where you downloaded the flatpak file.

4. Run the following command to install the flatpak package:

    ```bash
    flatpak install <path_to_flatpak_file>
    ```

5. Once the installation is complete, you can start the application by running:

    ```bash
    flatpak run com.covasnext.ui
    ```

6. The application should now start and you should see the main menu.
7. Open the advanced settings tab and scroll to the `Linux Settings` section at the bottom.
8. Configure the following settings:

    ```
        ED AppData Path: "/home/<username>/.steam/steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/AppData/Local/Frontier Developments/Elite Dangerous/"
        ED Journal Path: "/home/<username>/.steam/steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous"
    ```
    Depending on your system, the paths may be different. The above paths are for a steam + proton installation of the game.

9. In the General Settings tab, setup your input and output audio devices, it is recommended to use the virtual pulse devices.
10. Follow the regular [Getting Started](../index.md) guide to configure the rest of the application.
11. Start the AI and it should now work 🤞 If you have any issues, please contact us on discord.

## VR overlay

In **General Settings → Overlay**, select **VR Overlay** and turn on the content you want to see. Choose a voice provider if you want the avatar or chat to appear; with voice output set to **None**, both are hidden.

If COVAS:NEXT offers **Enable integration** or **Update integration**, select it and restart Elite Dangerous. Connect your headset, launch Elite in VR, and start the AI Assistant. Enabling integration by itself does not start the overlay.

If the overlay is still missing, use **Check again** in the VR overlay settings. **Waiting for a VR application** means COVAS:NEXT has not connected to Elite yet; **Connected to Elite Dangerous** means the VR connection is working, so check your overlay content settings.
