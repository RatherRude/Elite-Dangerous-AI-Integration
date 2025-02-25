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
        .stdout(std::process::Stdio::piped());

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
    let stdout = child.stdout.take().ok_or("Failed to take child stdout")?;
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
                            println!("Process stdout: {}", text);
                            if let Err(e) = window.emit("process-stdout", text) {
                                eprintln!("Failed to emit process-stdout event: {}", e);
                            }
                        } else {
                            eprintln!("Received invalid UTF-8 data");
                        }
                        buffer.clear();
                    }
                    Err(e) => {
                        eprintln!("Error reading stdout: {}", e);
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
    println!("Wrote to stdin: {}", json_line);
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
#[tokio::main]
pub async fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            start_process,
            stop_process,
            send_json_line
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
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
