#include <napi.h>
#include <windows.h>
#include <cstring>

class SharedMemory : public Napi::ObjectWrap<SharedMemory> {
public:
    static Napi::Object Init(Napi::Env env, Napi::Object exports);
    SharedMemory(const Napi::CallbackInfo& info);
    ~SharedMemory();

private:
    HANDLE m_handle;
    void* m_ptr;
    size_t m_size;
    
    Napi::Value Write(const Napi::CallbackInfo& info);
};

SharedMemory::SharedMemory(const Napi::CallbackInfo& info) 
    : Napi::ObjectWrap<SharedMemory>(info)
    , m_handle(nullptr)
    , m_ptr(nullptr)
    , m_size(0)
{
    Napi::Env env = info.Env();
    
    if (info.Length() < 2 || !info[0].IsString() || !info[1].IsNumber()) {
        Napi::TypeError::New(env, "Expected (name: string, size: number)").ThrowAsJavaScriptException();
        return;
    }
    
    std::string name = info[0].As<Napi::String>().Utf8Value();
    m_size = info[1].As<Napi::Number>().Uint32Value();
    
    // Try to open existing
    m_handle = OpenFileMappingA(FILE_MAP_ALL_ACCESS, FALSE, name.c_str());
    
    // Create if doesn't exist
    if (!m_handle) {
        m_handle = CreateFileMappingA(
            INVALID_HANDLE_VALUE,
            nullptr,
            PAGE_READWRITE,
            0,
            (DWORD)m_size,
            name.c_str()
        );
    }
    
    if (!m_handle) {
        Napi::Error::New(env, "Failed to create/open shared memory").ThrowAsJavaScriptException();
        return;
    }
    
    m_ptr = MapViewOfFile(m_handle, FILE_MAP_ALL_ACCESS, 0, 0, m_size);
    if (!m_ptr) {
        CloseHandle(m_handle);
        m_handle = nullptr;
        Napi::Error::New(env, "Failed to map shared memory").ThrowAsJavaScriptException();
        return;
    }
}

SharedMemory::~SharedMemory() {
    if (m_ptr) {
        UnmapViewOfFile(m_ptr);
    }
    if (m_handle) {
        CloseHandle(m_handle);
    }
}

Napi::Value SharedMemory::Write(const Napi::CallbackInfo& info) {
    Napi::Env env = info.Env();
    
    if (info.Length() < 2 || !info[0].IsBuffer() || !info[1].IsNumber()) {
        Napi::TypeError::New(env, "Expected (buffer: Buffer, offset: number)").ThrowAsJavaScriptException();
        return env.Undefined();
    }
    
    Napi::Buffer<uint8_t> buffer = info[0].As<Napi::Buffer<uint8_t>>();
    uint32_t offset = info[1].As<Napi::Number>().Uint32Value();
    
    if (offset + buffer.Length() > m_size) {
        Napi::Error::New(env, "Buffer too large for shared memory").ThrowAsJavaScriptException();
        return env.Undefined();
    }
    
    memcpy((uint8_t*)m_ptr + offset, buffer.Data(), buffer.Length());
    
    return env.Undefined();
}

Napi::Object SharedMemory::Init(Napi::Env env, Napi::Object exports) {
    Napi::Function func = DefineClass(env, "SharedMemory", {
        InstanceMethod("write", &SharedMemory::Write),
    });
    
    Napi::FunctionReference* constructor = new Napi::FunctionReference();
    *constructor = Napi::Persistent(func);
    env.SetInstanceData(constructor);
    
    exports.Set("SharedMemory", func);
    return exports;
}

Napi::Object InitModule(Napi::Env env, Napi::Object exports) {
    return SharedMemory::Init(env, exports);
}

NODE_API_MODULE(shared_memory, InitModule)