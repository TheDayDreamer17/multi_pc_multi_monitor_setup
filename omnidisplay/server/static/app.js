// OmniDisplay Web Client

let currentStatus = null;

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) throw new Error("Status HTTP " + res.status);
    const data = await res.json();
    currentStatus = data;
    render(data);
  } catch (err) {
    console.warn("Polling error:", err);
    document.getElementById("peer-text").innerText = "Connecting to local daemon...";
    document.getElementById("peer-status").className = "status-badge";
  }
}

function render(data) {
  // Update Role & Peer
  document.getElementById("node-role").innerText = data.role.toUpperCase();
  const peerBadge = document.getElementById("peer-status");
  const peerText = document.getElementById("peer-text");
  const peerEndpoint = document.getElementById("peer-endpoint");

  if (data.peer_online) {
    peerBadge.className = "status-badge online";
    peerText.innerText = `Connected (${data.peer_host})`;
    peerEndpoint.innerText = `${data.peer_host}:${data.peer_port}`;
  } else {
    peerBadge.className = "status-badge";
    peerText.innerText = "Waiting for peer...";
    peerEndpoint.innerText = "Searching LAN...";
  }

  // Update Left Monitor
  const leftHost = data.displays.left.active_host;
  const screenLeft = document.getElementById("screen-left");
  const hostLeft = document.getElementById("host-left");
  const toggleLeft = document.getElementById("toggle-target-left");

  hostLeft.innerText = leftHost.toUpperCase();
  screenLeft.className = "monitor-screen " + (leftHost === "mac" ? "active-mac" : "active-pc");
  toggleLeft.innerText = leftHost === "mac" ? "PC" : "Mac";

  // Update Right Monitor
  const rightHost = data.displays.right.active_host;
  const screenRight = document.getElementById("screen-right");
  const hostRight = document.getElementById("host-right");
  const toggleRight = document.getElementById("toggle-target-right");

  hostRight.innerText = rightHost.toUpperCase();
  screenRight.className = "monitor-screen " + (rightHost === "mac" ? "active-mac" : "active-pc");
  toggleRight.innerText = rightHost === "mac" ? "PC" : "Mac";

  // Update Preset Cards
  const activePreset = data.current_preset;
  document.querySelectorAll(".preset-card").forEach(card => card.classList.remove("active"));
  if (activePreset && activePreset !== "custom") {
    const activeEl = document.getElementById(`preset-${activePreset}`);
    if (activeEl) activeEl.classList.add("active");
  }
}

async function applyPreset(presetId) {
  try {
    const res = await fetch("/api/switch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preset: presetId })
    });
    if (res.ok) {
      fetchStatus();
    }
  } catch (e) {
    alert("Failed to switch preset: " + e.message);
  }
}

async function toggleDisplay(displayKey) {
  if (!currentStatus) return;
  const currentHost = currentStatus.displays[displayKey].active_host;
  const targetHost = currentHost === "mac" ? "pc" : "mac";

  try {
    const res = await fetch("/api/set_display", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display: displayKey, target_host: targetHost })
    });
    if (res.ok) {
      fetchStatus();
    }
  } catch (e) {
    alert("Failed to toggle display: " + e.message);
  }
}

// Global hotkeys 1-4
window.addEventListener("keydown", (e) => {
  // If user is not typing in an input
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

  switch (e.key) {
    case "1":
      applyPreset("pc_both");
      break;
    case "2":
      applyPreset("mac_both");
      break;
    case "3":
      applyPreset("split_pc_mac");
      break;
    case "4":
      applyPreset("split_mac_pc");
      break;
  }
});

// Initial fetch and 2-second polling loop
fetchStatus();
setInterval(fetchStatus, 2000);
