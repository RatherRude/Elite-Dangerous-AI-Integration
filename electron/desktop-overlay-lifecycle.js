function sameBounds(left, right) {
  return left && right
    && left.x === right.x
    && left.y === right.y
    && left.width === right.width
    && left.height === right.height;
}

export function selectOverlayDisplay(displays, primaryDisplay, screenId) {
  if (screenId !== -1) {
    const selectedDisplay = displays.find(display => display.id === screenId);
    if (selectedDisplay) {
      return selectedDisplay;
    }
  }
  return primaryDisplay;
}

export function normalizeDesktopOverlayScreen(screenId) {
  const requestedScreenId = Number.isInteger(screenId) ? screenId : -1;
  return {
    screenId: requestedScreenId === -2 ? -1 : requestedScreenId,
    desktopTarget: requestedScreenId === -2 ? 'elite-window' : 'monitor',
  };
}

export function createDesktopOverlayLifecycle({
  overlayWindow,
  nativeController: initialNativeController,
  options,
  getTargetDisplay,
  getOverlayBounds,
  logger,
  intervalMs = 1000,
  setIntervalFn = setInterval,
  clearIntervalFn = clearInterval,
}) {
  const parentQuery = {
    title: options.parentWindowName,
    match: 'contains',
  };
  let nativeController = initialNativeController;
  let placementTimer = null;
  let closed = false;
  let trackingParent = false;
  let parentErrorLogged = false;
  let capabilityWarningLogged = false;
  let lastFallbackBounds = null;

  const applyElectronPolicy = (display) => {
    const bounds = {
      x: Math.round(display.bounds.x),
      y: Math.round(display.bounds.y),
      width: Math.round(display.bounds.width),
      height: Math.round(display.bounds.height),
    };
    if (!sameBounds(lastFallbackBounds, bounds)) {
      overlayWindow.setBounds(bounds);
      lastFallbackBounds = bounds;
    }
    overlayWindow.setIgnoreMouseEvents(true);
    if (options.alwaysOnTop) {
      overlayWindow.setAlwaysOnTop(true, 'screen-saver', 2);
    } else {
      overlayWindow.setAlwaysOnTop(false);
    }
  };

  const disableNativeController = (error) => {
    if (!nativeController) {
      return;
    }
    logger.warn('Native desktop overlay controller failed; switching to Electron fallback:', error);
    try {
      nativeController.close();
    } catch (closeError) {
      logger.warn('Failed to close native desktop overlay controller:', closeError);
    }
    nativeController = null;
    trackingParent = false;
    lastFallbackBounds = null;
  };

  const applyMonitorBounds = () => {
    const display = getTargetDisplay();
    if (!nativeController) {
      applyElectronPolicy(display);
      return;
    }
    const bounds = getOverlayBounds(display);
    if (sameBounds(lastFallbackBounds, bounds)) {
      return;
    }
    try {
      nativeController.setBounds(bounds);
      lastFallbackBounds = bounds;
    } catch (error) {
      disableNativeController(error);
      applyElectronPolicy(display);
    }
  };

  const refresh = () => {
    if (closed || overlayWindow.isDestroyed()) {
      return;
    }
    if (!nativeController || options.desktopTarget !== 'elite-window') {
      applyMonitorBounds();
      return;
    }

    let capabilities;
    try {
      capabilities = nativeController.getCapabilities();
    } catch (error) {
      disableNativeController(error);
      applyMonitorBounds();
      return;
    }
    if (!capabilities.parentDiscovery) {
      if (!capabilityWarningLogged) {
        capabilityWarningLogged = true;
        logger.warn(`The ${capabilities.backend} overlay backend cannot discover the Elite window; using the selected monitor.`);
      }
      applyMonitorBounds();
      return;
    }

    try {
      const state = nativeController.getState();
      if (state.parent && nativeController.useParentBounds()) {
        trackingParent = true;
        parentErrorLogged = false;
        lastFallbackBounds = null;
        return;
      }

      if (state.parent) {
        nativeController.detachParent();
      }
      if (trackingParent) {
        logger.info('Elite window closed or became unavailable; using the selected monitor until it returns.');
        trackingParent = false;
      }
      applyMonitorBounds();

      const parent = nativeController.attachParent(parentQuery);
      if (parent && nativeController.useParentBounds()) {
        trackingParent = true;
        parentErrorLogged = false;
        lastFallbackBounds = null;
        logger.info('Tracking Elite window for desktop overlay:', {
          title: parent.title,
          className: parent.className,
          bounds: parent.bounds,
        });
      } else if (parent) {
        nativeController.detachParent();
      }
    } catch (error) {
      if (!parentErrorLogged) {
        parentErrorLogged = true;
        logger.warn('Elite window tracking failed; continuing discovery with monitor fallback:', error);
      }
      try {
        nativeController?.detachParent();
      } catch (detachError) {
        disableNativeController(detachError);
      }
      trackingParent = false;
      lastFallbackBounds = null;
      applyMonitorBounds();
    }
  };

  return {
    refresh,
    reapply() {
      if (!nativeController) {
        return;
      }
      try {
        nativeController.reapply();
      } catch (error) {
        disableNativeController(error);
        applyMonitorBounds();
      }
    },
    start() {
      if (closed || placementTimer) {
        return;
      }
      refresh();
      placementTimer = setIntervalFn(refresh, intervalMs);
      placementTimer?.unref?.();
    },
    close() {
      if (closed) {
        return;
      }
      closed = true;
      if (placementTimer) {
        clearIntervalFn(placementTimer);
        placementTimer = null;
      }
      try {
        nativeController?.close();
      } catch (error) {
        logger.warn('Failed to close native desktop overlay controller:', error);
      }
      nativeController = null;
    },
  };
}
