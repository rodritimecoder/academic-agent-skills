      let currentActiveVideo = null;

      function showZoomCard(zoomUrl, passcode, timeStr, title) {
        const zoomCard = document.getElementById("drawerZoomCard");
        if (!zoomCard) return;
        zoomCard.style.display = "block";
        const zTitle = document.getElementById("zoomCardTitle");
        const zTime = document.getElementById("zoomCardTime");
        const zPassBox = document.getElementById("zoomCardPasscodeBox");
        const zPassText = document.getElementById("zoomCardPasscodeText");
        const zBtn = document.getElementById("zoomCardLaunchBtn");

        if (zTitle) zTitle.textContent = title || "Zoom Cloud Recording";
        if (zTime) zTime.innerHTML = `Timestamp: <strong>${timeStr || "00:00:00"}</strong> <span style="font-size:11px; color:#a6adc8;">(Seek to this time in Zoom player)</span>`;
        if (passcode && zPassText && zPassBox) {
          zPassBox.style.display = "inline-block";
          zPassText.textContent = passcode;
        } else if (zPassBox) {
          zPassBox.style.display = "none";
        }
        if (zBtn) {
          zBtn.innerHTML = `<span>🚀</span> Copy Passcode &amp; Open Zoom`;
          zBtn.onclick = () => {
            if (passcode) {
              navigator.clipboard.writeText(passcode).then(() => {
                alert(`📋 Passcode "${passcode}" copied to clipboard! Opening Zoom...`);
              }).catch(() => {});
            }
            window.open(zoomUrl, "_blank");
          };
        }
      }
      window.showZoomCard = showZoomCard;

      function openVideoClip(videoData) {
        if (!videoData) return;
        currentActiveVideo = videoData;

        const drawer = document.getElementById("videoDrawer");
        const titleEl = document.getElementById("videoDrawerTitleText");
        const timePill = document.getElementById("videoDrawerTimePill");
        const mp4El = document.getElementById("drawerMp4Player");
        const ytEl = document.getElementById("drawerYtPlayer");
        const zoomCard = document.getElementById("drawerZoomCard");

        if (!drawer) return;

        drawer.style.display = "flex";
        drawer.classList.remove("minimized");
        if (mp4El) {
          mp4El.pause();
          mp4El.onerror = null;
          mp4El.style.display = "none";
          mp4El.src = "";
        }
        if (ytEl) {
          ytEl.style.display = "none";
          ytEl.src = "about:blank";
        }
        if (zoomCard) {
          zoomCard.style.display = "none";
        }

        const vSrc = videoData.src || videoData.url || "";
        let vType = videoData.type;
        if (!vType) {
          if (vSrc.includes("youtube.com") || vSrc.includes("youtu.be")) vType = "youtube";
          else if (vSrc.includes("zoom.us")) vType = "zoom";
          else if (vSrc.toLowerCase().endsWith(".mp4")) vType = "mp4";
          else if (videoData.passcode) vType = "zoom";
          else vType = "zoom";
        }

        // Intercept accidental .vtt or .md files supplied as video sources and redirect them to Zoom
        if (vSrc.toLowerCase().endsWith(".vtt") || vSrc.toLowerCase().endsWith(".md")) {
          vType = "zoom";
        }

        const seekSec = videoData.seconds !== undefined ? Number(videoData.seconds) : (videoData.timestamp !== undefined ? Number(videoData.timestamp) : 0);
        let timeStr = videoData.time_str;
        if (!timeStr) {
          const m = Math.floor(seekSec / 60);
          const s = Math.floor(seekSec % 60);
          timeStr = `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
        }

        const displayTitle = videoData.title || videoData.label || "Solution Video";
        if (titleEl) titleEl.textContent = displayTitle;
        if (timePill) timePill.textContent = timeStr;

        if (vType === "youtube") {
          if (window.location.protocol === "file:") {
            if (zoomCard) {
              zoomCard.style.display = "block";
              const zTitle = document.getElementById("zoomCardTitle");
              const zTime = document.getElementById("zoomCardTime");
              const zPassBox = document.getElementById("zoomCardPasscodeBox");
              const zLaunchBtn = document.getElementById("zoomCardLaunchBtn");

              if (zTitle) zTitle.textContent = "YouTube Walkthrough Clip";
              if (zTime) zTime.innerHTML = `Timestamp: <strong>${timeStr}</strong><br><span style="font-size:11px; color:#a6adc8; margin-top:5px; display:inline-block;">YouTube blocks in-app embeds from <code>file://</code> URLs.<br>Run <code>./serve.sh</code> for in-drawer playback, or click below:</span>`;
              if (zPassBox) zPassBox.style.display = "none";
              if (zLaunchBtn) {
                zLaunchBtn.innerHTML = `<span>🚀</span> Watch on YouTube (${timeStr})`;
                const rawYt = vSrc.replace("www.youtube-nocookie.com/embed/", "www.youtube.com/watch?v=").replace("&autoplay=1", "").replace("?autoplay=1", "");
                zLaunchBtn.onclick = () => window.open(rawYt, "_blank");
              }
            }
          } else if (ytEl) {
            ytEl.style.display = "block";
            ytEl.src = vSrc;
          }
        } else if (vType === "mp4" && mp4El) {
          mp4El.style.display = "block";
          mp4El.onerror = () => {
            console.warn("Local MP4 stream failed or not found, falling back to Zoom Card:", vSrc);
            mp4El.style.display = "none";
            showZoomCard(videoData.fallbackSrc || vSrc, videoData.passcode, timeStr, displayTitle);
          };
          mp4El.src = vSrc;
          mp4El.currentTime = seekSec;
          mp4El.play().catch(() => {});
        } else if (vType === "zoom" && zoomCard) {
          showZoomCard(vSrc, videoData.passcode, timeStr, displayTitle);
        }
      }
      window.openVideoClip = openVideoClip;

      function openVideoClipFromStr(jsonStr) {
        try {
          const data = JSON.parse(jsonStr);
          openVideoClip(data);
        } catch (err) {
          console.error("Failed to parse video clip data", err);
        }
      }
      window.openVideoClipFromStr = openVideoClipFromStr;

      function closeVideoDrawer() {
        const drawer = document.getElementById("videoDrawer");
        const mp4El = document.getElementById("drawerMp4Player");
        const ytEl = document.getElementById("drawerYtPlayer");
        if (mp4El) {
          mp4El.pause();
          mp4El.src = "";
        }
        if (ytEl) {
          ytEl.src = "about:blank";
        }
        if (drawer) drawer.style.display = "none";
        currentActiveVideo = null;
      }
      window.closeVideoDrawer = closeVideoDrawer;


      function toggleVideoDrawerMinimize() {
        const drawer = document.getElementById("videoDrawer");
        if (drawer) drawer.classList.toggle("minimized");
      }
      window.toggleVideoDrawerMinimize = toggleVideoDrawerMinimize;

      function launchZoomWithPasscode() {
        if (!currentActiveVideo || currentActiveVideo.type !== "zoom") return;
        if (currentActiveVideo.passcode) {
          navigator.clipboard.writeText(currentActiveVideo.passcode).then(() => {
            alert(`📋 Passcode "${currentActiveVideo.passcode}" copied to clipboard! Opening Zoom...`);
          }).catch(() => {});
        }
        window.open(currentActiveVideo.src, "_blank");
      }
      window.launchZoomWithPasscode = launchZoomWithPasscode;

