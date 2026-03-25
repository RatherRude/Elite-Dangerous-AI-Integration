#include <openvr.h>
#include <d3d11.h>
#include <dxgi.h>
#include <wrl/client.h>
#include <iostream>
#include <thread>
#include <chrono>
#include <windows.h>

using Microsoft::WRL::ComPtr;

struct SharedMemoryHeader {
    uint32_t width;
    uint32_t height;
    uint32_t frameNumber;
    bool ready;
    float posX;
    float posY;
    float posZ;
    float overlayWidth;
    float curvature;  // ADD THIS - 0.0 = flat, higher = more curved
};

const char* SHARED_MEMORY_NAME = "CovasVROverlaySharedMemory";  // Remove "Global\\"
const size_t MAX_TEXTURE_SIZE = 3840 * 2160 * 4; // 4K RGBA
const size_t SHARED_MEMORY_SIZE = sizeof(SharedMemoryHeader) + MAX_TEXTURE_SIZE;

class VROverlayApp {
public:
    VROverlayApp() 
        : m_overlay(vr::k_ulOverlayHandleInvalid)
        , m_sharedMemHandle(nullptr)
        , m_sharedMemPtr(nullptr)
        , m_lastFrameNumber(0)
    {}
    
    ~VROverlayApp() {
        Shutdown();
    }
    
    bool Initialize() {
        std::cout << "[VROverlay] Initializing OpenVR..." << std::endl;
        
        // Initialize OpenVR
        vr::EVRInitError error = vr::VRInitError_None;
        m_vrSystem = vr::VR_Init(&error, vr::VRApplication_Overlay);
        
        if (error != vr::VRInitError_None) {
            std::cerr << "Failed to initialize OpenVR: " << vr::VR_GetVRInitErrorAsEnglishDescription(error) << std::endl;
            return false;
        }
        
        std::cout << "[VROverlay] OpenVR initialized" << std::endl;
        
        // Initialize D3D11
        if (!InitializeD3D11()) {
            return false;
        }
        
        // Create shared memory
        if (!InitializeSharedMemory()) {
            return false;
        }
        
        // Create overlay
        if (!CreateOverlay()) {
            return false;
        }
        
        std::cout << "[VROverlay] Initialization complete" << std::endl;
        return true;
    }
    
    void Run() {
        std::cout << "[VROverlay] Entering main loop..." << std::endl;
        
        while (true) {
            // Process VR events
            vr::VREvent_t event;
            while (m_vrSystem->PollNextEvent(&event, sizeof(event))) {
                if (event.eventType == vr::VREvent_Quit) {
                    return;
                }
            }
            
            // Update texture from shared memory
            UpdateTextureFromSharedMemory();
            
            // Sleep to avoid burning CPU
            std::this_thread::sleep_for(std::chrono::milliseconds(16)); // ~60fps
        }
    }
    
    void Shutdown() {
        std::cout << "[VROverlay] Shutting down..." << std::endl;
        
        if (m_overlay != vr::k_ulOverlayHandleInvalid) {
            vr::VROverlay()->DestroyOverlay(m_overlay);
        }
        
        if (m_sharedMemPtr) {
            UnmapViewOfFile(m_sharedMemPtr);
        }
        
        if (m_sharedMemHandle) {
            CloseHandle(m_sharedMemHandle);
        }
        
        if (m_vrSystem) {
            vr::VR_Shutdown();
        }
    }

private:
    bool InitializeD3D11() {
        std::cout << "[VROverlay] Initializing D3D11..." << std::endl;
        
        D3D_FEATURE_LEVEL featureLevel;
        HRESULT hr = D3D11CreateDevice(
            nullptr,
            D3D_DRIVER_TYPE_HARDWARE,
            nullptr,
            0,
            nullptr,
            0,
            D3D11_SDK_VERSION,
            &m_d3dDevice,
            &featureLevel,
            &m_d3dContext
        );
        
        if (FAILED(hr)) {
            std::cerr << "Failed to create D3D11 device" << std::endl;
            return false;
        }
        
        // Print GPU info
        ComPtr<IDXGIDevice> dxgiDevice;
        m_d3dDevice->QueryInterface(__uuidof(IDXGIDevice), (void**)&dxgiDevice);
        
        ComPtr<IDXGIAdapter> adapter;
        dxgiDevice->GetAdapter(&adapter);
        
        DXGI_ADAPTER_DESC adapterDesc;
        adapter->GetDesc(&adapterDesc);
        
        std::wcout << L"[VROverlay] Using GPU: " << adapterDesc.Description << std::endl;
        
        return true;
    }
    
    bool InitializeSharedMemory() {
        std::cout << "[VROverlay] Creating shared memory..." << std::endl;
        
        // Create shared memory
        m_sharedMemHandle = CreateFileMappingA(
            INVALID_HANDLE_VALUE,
            nullptr,
            PAGE_READWRITE,
            0,
            SHARED_MEMORY_SIZE,
            SHARED_MEMORY_NAME
        );
        
        if (!m_sharedMemHandle) {
            std::cerr << "Failed to create shared memory" << std::endl;
            return false;
        }
        
        // Map view
        m_sharedMemPtr = MapViewOfFile(
            m_sharedMemHandle,
            FILE_MAP_ALL_ACCESS,
            0,
            0,
            SHARED_MEMORY_SIZE
        );
        
        if (!m_sharedMemPtr) {
            std::cerr << "Failed to map shared memory" << std::endl;
            return false;
        }
        
        // Initialize header
        SharedMemoryHeader* header = (SharedMemoryHeader*)m_sharedMemPtr;
        header->width = 0;
        header->height = 0;
        header->frameNumber = 0;
        header->ready = false;
        
        std::cout << "[VROverlay] Shared memory created: " << SHARED_MEMORY_NAME << std::endl;
        
        return true;
    }
    
    bool CreateOverlay() {
        std::cout << "[VROverlay] Creating overlay..." << std::endl;
        
        vr::VROverlayError error = vr::VROverlay()->CreateOverlay(
            "covas.overlay",
            "COVAS:NEXT",
            &m_overlay
        );
        
        if (error != vr::VROverlayError_None) {
            std::cerr << "Failed to create overlay" << std::endl;
            return false;
        }
        
        // Set overlay properties
        vr::VROverlay()->SetOverlayWidthInMeters(m_overlay, 1.5f);
        
        // Position in front of user
        vr::HmdMatrix34_t transform = {
            1.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 1.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 1.0f, -2.0f
        };
        vr::VROverlay()->SetOverlayTransformAbsolute(m_overlay, vr::TrackingUniverseStanding, &transform);
        
        // Show overlay
        vr::VROverlay()->ShowOverlay(m_overlay);
        
        std::cout << "[VROverlay] Overlay created and visible" << std::endl;
        
        return true;
    }
    
    bool CreateTexture(uint32_t width, uint32_t height) {
        D3D11_TEXTURE2D_DESC desc = {};
        desc.Width = width;
        desc.Height = height;
        desc.MipLevels = 1;
        desc.ArraySize = 1;
        desc.Format = DXGI_FORMAT_B8G8R8A8_UNORM;
        desc.SampleDesc.Count = 1;
        desc.Usage = D3D11_USAGE_DYNAMIC;
        desc.BindFlags = D3D11_BIND_SHADER_RESOURCE;
        desc.CPUAccessFlags = D3D11_CPU_ACCESS_WRITE;
        
        HRESULT hr = m_d3dDevice->CreateTexture2D(&desc, nullptr, &m_texture);
        if (FAILED(hr)) {
            std::cerr << "Failed to create texture" << std::endl;
            return false;
        }
        
        m_textureWidth = width;
        m_textureHeight = height;
        
        std::cout << "[VROverlay] Created texture: " << width << "x" << height << std::endl;
        
        return true;
    }
    
  void UpdateTextureFromSharedMemory() {
    SharedMemoryHeader* header = (SharedMemoryHeader*)m_sharedMemPtr;
    
    // Check if new frame is available
    if (!header->ready || header->frameNumber == m_lastFrameNumber) {
        return;
    }
    
    // Update position if it changed
    vr::HmdMatrix34_t transform = {
        1.0f, 0.0f, 0.0f, header->posX,
        0.0f, 1.0f, 0.0f, header->posY,
        0.0f, 0.0f, 1.0f, header->posZ
    };
    vr::VROverlay()->SetOverlayTransformAbsolute(m_overlay, vr::TrackingUniverseStanding, &transform);
    vr::VROverlay()->SetOverlayWidthInMeters(m_overlay, header->overlayWidth);
    vr::VROverlay()->SetOverlayCurvature(m_overlay, header->curvature);  // ADD THIS
    
    // Create or recreate texture if size changed
    if (!m_texture || header->width != m_textureWidth || header->height != m_textureHeight) {
        m_texture.Reset();
        if (!CreateTexture(header->width, header->height)) {
            return;
        }
    }
    
    // Map texture
    D3D11_MAPPED_SUBRESOURCE mapped;
    HRESULT hr = m_d3dContext->Map(m_texture.Get(), 0, D3D11_MAP_WRITE_DISCARD, 0, &mapped);
    if (FAILED(hr)) {
        return;
    }
    
    // Copy pixel data
    uint8_t* src = (uint8_t*)m_sharedMemPtr + sizeof(SharedMemoryHeader);
    uint8_t* dst = (uint8_t*)mapped.pData;
    uint32_t srcPitch = header->width * 4;
    
    for (uint32_t y = 0; y < header->height; y++) {
        memcpy(dst + y * mapped.RowPitch, src + y * srcPitch, srcPitch);
    }
    
    m_d3dContext->Unmap(m_texture.Get(), 0);
    
    // Set overlay texture
    vr::Texture_t vrTexture = {
        m_texture.Get(),
        vr::TextureType_DirectX,
        vr::ColorSpace_Auto
    };
    
    vr::VROverlay()->SetOverlayTexture(m_overlay, &vrTexture);
    
    m_lastFrameNumber = header->frameNumber;
    
    static int frameCount = 0;
    if (++frameCount % 60 == 0) {
        std::cout << "[VROverlay] Updated frame " << m_lastFrameNumber 
                  << " at (" << header->posX << ", " << header->posY << ", " << header->posZ << ")" << std::endl;
    }
}

    vr::IVRSystem* m_vrSystem = nullptr;
        vr::VROverlayHandle_t m_overlay;
        
        ComPtr<ID3D11Device> m_d3dDevice;
        ComPtr<ID3D11DeviceContext> m_d3dContext;
        ComPtr<ID3D11Texture2D> m_texture;
        
        uint32_t m_textureWidth = 0;
        uint32_t m_textureHeight = 0;
        
        HANDLE m_sharedMemHandle;
        void* m_sharedMemPtr;
        uint32_t m_lastFrameNumber;
    };  // ← Close the class here
int main() {
    std::cout << "COVAS:NEXT VR Overlay (Shared Memory)" << std::endl;
    std::cout << "======================================" << std::endl;
    
    VROverlayApp app;
    
    if (!app.Initialize()) {
        std::cerr << "Failed to initialize" << std::endl;
        return 1;
    }
    
    app.Run();
    
    return 0;
}