/**
 * AI Virtual Try-On - Background Service Worker (Manifest V3)
 * Handles extension lifecycle, side panel management, and inter-component messaging.
 */

// Configure default side panel behavior upon extension installation
chrome.runtime.onInstalled.addListener(() => {
  console.log('[AI Try-On] Extension installed successfully.');
  
  if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
    // Keep default action opening the popup, while allowing direct side panel opening
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false })
      .catch((error) => console.error('[AI Try-On] Error setting panel behavior:', error));
  }
});

// Listen for messages from popup or content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'OPEN_SIDE_PANEL') {
    // Open the side panel for the active tab or current window
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const activeTab = tabs[0];
      if (activeTab && activeTab.id) {
        chrome.sidePanel.open({ tabId: activeTab.id })
          .then(() => sendResponse({ success: true }))
          .catch((err) => {
            console.error('[AI Try-On] Failed to open side panel:', err);
            sendResponse({ success: false, error: err.message });
          });
      } else {
        chrome.sidePanel.open({ windowId: sender.tab?.windowId })
          .then(() => sendResponse({ success: true }))
          .catch((err) => sendResponse({ success: false, error: err.message }));
      }
    });
    return true; // Keep message channel open for async response
  }

  if (message.type === 'GET_BACKEND_STATUS') {
    // Proxy health checks if needed
    fetch('http://localhost:8000/health')
      .then((res) => res.json())
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }
});
