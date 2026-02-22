# Plugins

COVAS:NEXT offers an extensive plugin API, which allows 3rd parties to extend the functionality of your assistant, integrating it with various other tools, or just adding additional features.

# First Official Plugins

| Plugin | Description | Releases |
|--------|-------------|----------|
| **Parakeet** | Free, local STT Plugin (Multilingual) | [Releases](https://github.com/COVAS-Labs/plugin-parakeet-stt/releases) |
| **Supertonic** | Free, local TTS Plugin (Multilingual) | [Releases](https://github.com/COVAS-Labs/plugin-supertonic-tts/releases) |
| **Gemma** | Free, local Embedding Plugin (Multilingual) | [Releases](https://github.com/COVAS-Labs/plugin-gemma-embedding/releases) |
| **Elevenlabs** | Paid, Cloud STT&TTS Plugin (Multilingual) | [Releases](https://github.com/COVAS-Labs/plugin-elevenlabs/releases) |

# Plugin installation
All plugins are installed in the `plugins` folder, found here:  

* Windows: `%appdata%\com.covas-next.ui\plugins`
* Linux: `~/.var/app/com.covasnext.ui/data/com.covas-next.ui/plugins`

To install a plugin, download the packaged plugin archive and extract it to a subfolder inside the `plugins` directory.  
Ensure that the manifest is found at `C:/Users/USERNAME/AppData/Roaming/com.covas-next.ui/plugins/SUB-FOLDER/manifest.json`, otherwise the plugin will not load.

# For developers
See the [Development](./Development.md) page.
