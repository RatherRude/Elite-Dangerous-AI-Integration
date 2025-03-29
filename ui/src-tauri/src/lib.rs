use log::{debug, error, info};
use std::env;
use std::sync::Arc;
use tauri::path::BaseDirectory;
use tauri::Emitter;
use tauri::Manager;
use tauri::State;
use tokio::io::AsyncBufReadExt;
use tokio::io::{AsyncWriteExt, BufReader};
use tokio::process::{Child, ChildStdin, Command};
use tokio::sync::Mutex;

#[cfg(windows)]
use windows::Win32::Foundation::HWND;
#[cfg(windows)]
use windows::Win32::UI::WindowsAndMessaging::AllowSetForegroundWindow;

// Define a function to get the commit hash, which will be set at build time
// If not set, it will default to "development"
fn get_commit_hash_value() -> &'static str {
    option_env!("COMMIT_HASH").unwrap_or("development")
}

const DEV_EXE_PATH: &str = "python";
const DEV_EXE_CWD: &str = "../..";
const DEV_EXE_ARGS: &[&str] = &["-u", "./src/Chat.py"];

const PROD_EXE_ARGS: &[&str] = &[];

fn get_exe_config(
    window: &tauri::Window,
) -> Result<(String, String, &'static [&'static str]), String> {
    if cfg!(debug_assertions) {
        Ok((
            DEV_EXE_PATH.to_string(),
            DEV_EXE_CWD.to_string(),
            DEV_EXE_ARGS,
        ))
    } else {
        let app_handle = window.app_handle();
        let resource_path = app_handle
            .path()
            .resolve("resources/Chat", BaseDirectory::Resource)
            .map_err(|e| format!("Failed to resolve Chat executable: {}", e))?
            .to_str()
            .ok_or("Failed to convert resource path to string")?
            .to_string();

        let working_path = app_handle
            .path()
            .resolve("resources", BaseDirectory::Resource)
            .map_err(|e| format!("Failed to resolve Chat executable working directory: {}", e))?
            .to_str()
            .ok_or("Failed to convert working path to string")?
            .to_string();

        Ok((resource_path, working_path, PROD_EXE_ARGS))
    }
}

struct ProcessHandle {
    child: Child,
    stdin: Arc<tokio::sync::Mutex<ChildStdin>>,
}

#[derive(Default)]
struct AppState {
    process_handle: Arc<tokio::sync::Mutex<Option<ProcessHandle>>>,
}

// Helper function to check if a string contains sensitive information
fn contains_sensitive_data(text: &str) -> bool {
    false
        || text.to_lowercase().contains("api_key")
        || text.to_lowercase().contains("\"type\":\"config\"")
        || text.to_lowercase().contains("\"type\":\"change_config\"")
}

#[tauri::command]
async fn start_process(window: tauri::Window, state: State<'_, AppState>) -> Result<(), String> {
    let mut proc_handle_lock = state.process_handle.lock().await;
    if proc_handle_lock.is_some() {
        return Err("Process already running.".into());
    }

    let (exe_path, exe_cwd, exe_args) = get_exe_config(&window)?;

    let mut command = Command::new(exe_path.clone());
    command
        .args(exe_args)
        .current_dir(exe_cwd.clone())
        .kill_on_drop(true)
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped());

    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000); // CREATE_NO_WINDOW
    }

    let mut child = command.spawn().map_err(|e| {
        format!(
            "Failed to spawn process: {} - {} in {}",
            e, exe_path, exe_cwd
        )
    })?;

    #[cfg(windows)]
    {
        // Allow the child process to set foreground window
        let pid = child.id().expect("Failed to get process ID");
        unsafe {
            if let Err(e) = AllowSetForegroundWindow(pid as i32) {
                debug!("Failed to call AllowSetForegroundWindow: {:?}", e);
            } else {
                debug!(
                    "Successfully called AllowSetForegroundWindow for PID: {}",
                    pid
                );
            }
        }
    }

    let stdout = child.stdout.take().ok_or("Failed to take child stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to take child stderr")?;
    let stdin = child.stdin.take().ok_or("Failed to take child stdin")?;
    let stdin = Arc::new(Mutex::new(stdin));
    tokio::spawn({
        let window = window.clone();
        async move {
            let mut reader = BufReader::new(stdout);
            let mut buffer = Vec::new();
            loop {
                match reader.read_until(b'\n', &mut buffer).await {
                    Ok(0) => break, // EOF reached
                    Ok(_n) => {
                        if let Ok(text) = String::from_utf8(buffer.clone()) {
                            // Check if the output contains sensitive information
                            if contains_sensitive_data(&text) {
                                debug!("Process stdout: [REDACTED SENSITIVE DATA]");
                            } else {
                                debug!("Process stdout: {}", text);
                            }

                            // Always emit the actual data to the window, the redaction is only for logs
                            if let Err(e) = window.emit("process-stdout", text) {
                                error!("Failed to emit process-stdout event: {}", e);
                            }
                        } else {
                            error!("Received invalid UTF-8 data");
                        }
                        buffer.clear();
                    }
                    Err(e) => {
                        error!("Error reading stdout: {}", e);
                        break;
                    }
                }
            }
        }
    });
    tokio::spawn({
        let window = window.clone();
        async move {
            let mut reader = BufReader::new(stderr);
            let mut buffer = Vec::new();
            loop {
                match reader.read_until(b'\n', &mut buffer).await {
                    Ok(0) => break, // EOF reached

                    Ok(_n) => {
                        if let Ok(text) = String::from_utf8(buffer.clone()) {
                            // Check if the output contains sensitive information
                            if contains_sensitive_data(&text) {
                                debug!("Process stderr: [REDACTED SENSITIVE DATA]");
                            } else {
                                debug!("Process stderr: {}", text);
                            }

                            // Always emit the actual data to the window, the redaction is only for logs
                            if let Err(e) = window.emit("process-stderr", text) {
                                error!("Failed to emit process-stderr event: {}", e);
                            }
                        } else {
                            error!("Received invalid UTF-8 data");
                        }
                        buffer.clear();
                    }
                    Err(e) => {
                        error!("Error reading stdout: {}", e);
                        break;
                    }
                }
            }
        }
    });

    let handle = ProcessHandle { child, stdin };
    *proc_handle_lock = Some(handle);
    Ok(())
}

#[tauri::command]
async fn send_json_line(state: State<'_, AppState>, json_line: String) -> Result<(), String> {
    let stdin_arc = {
        let proc_handle_lock = state.process_handle.lock().await;
        let process = proc_handle_lock.as_ref().ok_or("Process is not running.")?;
        process.stdin.clone()
    };
    let mut stdin_guard = stdin_arc.lock().await;
    stdin_guard
        .write_all(json_line.as_bytes())
        .await
        .map_err(|e| format!("Failed to write to stdin: {}", e))?;
    stdin_guard
        .flush()
        .await
        .map_err(|e| format!("Failed to flush stdin: {}", e))?;

    // Check if the input contains sensitive information
    if contains_sensitive_data(&json_line) {
        debug!("Wrote to stdin: [REDACTED SENSITIVE DATA]");
    } else {
        debug!("Wrote to stdin: {}", json_line);
    }

    Ok(())
}

#[tauri::command]
async fn stop_process(state: State<'_, AppState>) -> Result<(), String> {
    let mut proc_handle_lock = state.process_handle.lock().await;
    if let Some(handle) = proc_handle_lock.as_mut() {
        if let Err(e) = handle.child.kill().await {
            return Err(format!("Failed to kill process: {}", e));
        }
    }
    *proc_handle_lock = None;
    Ok(())
}

#[tauri::command]
fn get_commit_hash() -> String {
    get_commit_hash_value().to_string()
}

#[tauri::command]
async fn create_floating_overlay(app_handle: tauri::AppHandle) -> Result<(), String> {
    let mut window_builder = tauri::WebviewWindowBuilder::new(
        &app_handle,
        "overlay",
        tauri::WebviewUrl::App("index.html#/overlay".into()),
    );
    // First, get a reference to the main window
    let main_window = app_handle
        .get_webview_window("main")
        .ok_or_else(|| "Main window not found".to_string())?;

    window_builder = window_builder
        .title("COVAS:NEXT Overlay")
        .inner_size(480.0, 480.0)
        .decorations(false)
        .transparent(true)
        .always_on_top(true)
        .skip_taskbar(false)
        .maximized(true)
        //.fullscreen(true)
        .visible(true);

    let window = window_builder
        .parent(&main_window)
        .map_err(|e| format!("Failed to assign parent window: {}", e))?
        .build()
        .map_err(|e| format!("Failed to create floating overlay window: {}", e))?;

    // Make the window non-clickable (ignore cursor events)
    window
        .set_ignore_cursor_events(true)
        .map_err(|e| format!("Failed to set window to ignore cursor events: {}", e))?;

    info!("Created floating overlay window");

    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
#[tokio::main]
pub async fn run() {
    // Logging will be initialized by the plugin

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(
            tauri_plugin_log::Builder::default()
                .rotation_strategy(tauri_plugin_log::RotationStrategy::KeepAll)
                .build(),
        )
        .manage(AppState {
            process_handle: Arc::new(Mutex::new(None)),
        })
        .invoke_handler(tauri::generate_handler![
            start_process,
            stop_process,
            send_json_line,
            get_commit_hash,
            create_floating_overlay
        ])
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let handle = window.app_handle().clone();
                tokio::spawn(async move {
                    let state: State<'_, AppState> = handle.state();
                    let _ = stop_process(state).await;
                });
            }
        })
        .setup(|_app| {
            // Log startup information after the plugin is initialized
            info!(
                "Starting application with commit hash: {}",
                get_commit_hash_value()
            );
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application");

    app.run(|_app_handle, _event| {});
}
