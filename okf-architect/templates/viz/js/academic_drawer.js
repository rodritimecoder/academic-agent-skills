      function selectNode(n) {
        selectedNode = n;
        requestRender();

        const drawer = document.getElementById("detailsDrawer");
        drawer.classList.add("open");

        document.getElementById("dTitle").textContent = n.cleanTitle;
        document.getElementById("dId").textContent = n.id;
        document.getElementById("dTrust").textContent = n.trust;
        document.getElementById("dDesc").textContent = n.description || "Comprehensive notes, derivations, and examples for this module.";

        // Cornell Interactive Button
        const cBlock = document.getElementById("dCornellBlock");
        const cLink = /** @type {HTMLAnchorElement | null} */ (document.getElementById("dCornellLink"));
        const cCues = document.getElementById("dCornellCues");
        if (n.hasCornell && n.cornellPath) {
          cBlock.style.display = "block";
          let safeUrl = encodeURI(n.cornellPath);
          if (window.location.protocol === "file:") {
            const baseDir = window.location.href.substring(0, window.location.href.lastIndexOf("/") + 1);
            safeUrl = baseDir + encodeURI(n.cornellPath);
          }
          if (cLink) {
            cLink.href = safeUrl;
            cLink.onclick = function(e) {
              e.preventDefault();
              openCornellModal(safeUrl, n.cleanTitle, n.id);
            };
          }
          if (cCues) cCues.textContent = String(n.cornellCues || 0);
        } else {
          cBlock.style.display = "none";
          if (cLink) cLink.onclick = null;
        }

        // Academic Trinity: Dynamic PDF Problem Sheet & Solution Cues
        const pdfBlock = document.getElementById("dPdfBlock");
        const pdfBtn = document.getElementById("dPdfBtn");
        const cuesBlock = document.getElementById("dSolutionCuesBlock");
        const cuesList = document.getElementById("dSolutionCuesList");

        const cleanId = (n.id || "").toLowerCase();
        let targetPdf = null;
        let matchedSolKey = null;

        for (const solKey of Object.keys(WORKED_SOLUTIONS_DB)) {
          if (cleanId.includes(solKey)) {
            matchedSolKey = solKey;
            break;
          }
        }

        if (matchedSolKey && WORKED_SOLUTIONS_DB[matchedSolKey].pdfPath) {
          targetPdf = WORKED_SOLUTIONS_DB[matchedSolKey].pdfPath;
        } else if (cleanId.includes("48520") && cleanId.includes("week_2")) {
          targetPdf = "48520 - Electronics and Circuits/Week_2/Week_2_Topic_Notes.pdf";
        }

        if (pdfBlock && pdfBtn) {
          if (targetPdf) {
            pdfBlock.style.display = "block";
            pdfBtn.onclick = function() {
              openPdfModal(targetPdf, n.cleanTitle + " (Problem Sheet)");
            };
          } else {
            pdfBlock.style.display = "none";
            pdfBtn.onclick = null;
          }
        }

        // Solution Cues
        if (cuesBlock && cuesList) {
          if (matchedSolKey && WORKED_SOLUTIONS_DB[matchedSolKey]) {
            const solData = WORKED_SOLUTIONS_DB[matchedSolKey];
            cuesBlock.style.display = "block";
            cuesList.innerHTML = "";
            solData.cues.forEach(cue => {
              const btn = document.createElement("button");
              btn.className = "solution-cue-btn";
              btn.innerHTML = `<span>▶ ${cue.label}</span><span class="solution-time-badge">${cue.time}</span>`;
              btn.onclick = function() {
                openVideoClip({
                  title: solData.title,
                  label: cue.label,
                  src: solData.videoSrc,
                  fallbackSrc: solData.fallbackSrc,
                  type: solData.type,
                  passcode: solData.passcode,
                  seconds: cue.seconds,
                  timestamp: cue.seconds,
                  time_str: cue.time
                });
              };
              cuesList.appendChild(btn);
            });
          } else {
            cuesBlock.style.display = "none";
            cuesList.innerHTML = "";
          }
        }

        // Anki Flashcard Button in Drawer
        const aBlock = document.getElementById("dAnkiBlock");
        const aBtn = document.getElementById("dAnkiBtn");
        const aCount = document.getElementById("dAnkiCount");
        if (n.cornellCards && n.cornellCards.length > 0) {
          aBlock.style.display = "block";
          aCount.textContent = n.cornellCards.length;
          aBtn.onclick = function() {
            startAnkiSession("node", n);
          };
        } else {
          aBlock.style.display = "none";
          aBtn.onclick = null;
        }

        const cTheme = COURSE_THEMES[n.course] || COURSE_THEMES["General"];
        const badge = document.getElementById("dCourseBadge");
        badge.textContent = cTheme.name;
        badge.style.color = cTheme.color;
        badge.style.borderColor = cTheme.color;

        // Tags
        const tagsContainer = document.getElementById("dTags");
        tagsContainer.innerHTML = "";
        if (n.tags && n.tags.length > 0) {
          n.tags.forEach(t => {
            const p = document.createElement("span");
            p.className = "pill";
            p.textContent = t;
            tagsContainer.appendChild(p);
          });
        } else {
          tagsContainer.textContent = "None";
        }

        // Connections List
        const linksList = document.getElementById("dLinks");
        linksList.innerHTML = "";
        const visibleNeighbors = Array.from(n.neighbors).filter(nbr => {
          if (currentViewMode === "semantic" && nbr.type === "ModuleHub") return false;
          return true;
        });
        const dLinkCountEl = document.getElementById("dLinkCount");
        if (dLinkCountEl) dLinkCountEl.textContent = String(visibleNeighbors.length);

        visibleNeighbors.forEach(nbr => {
          const li = document.createElement("li");
          li.className = "conn-item";
          const nbrTheme = COURSE_THEMES[nbr.course] || COURSE_THEMES["General"];
          li.innerHTML = `<span class="conn-arrow" style="color:${nbrTheme.color}">&#8594;</span> <span>${nbr.cleanTitle}</span>`;
          li.onclick = () => {
            d3.select(canvas).transition().duration(600).call(
              zoom.transform,
              d3.zoomIdentity.translate(width / 2, height / 2).scale(1.2).translate(-nbr.x, -nbr.y)
            );
            selectNode(nbr);
          };
          linksList.appendChild(li);
        });
      }

      document.getElementById("drawerClose").onclick = () => {
        document.getElementById("detailsDrawer").classList.remove("open");
        selectedNode = null;
        requestRender();
      };

      // Reset View Button
      document.getElementById("resetBtn").onclick = () => {
        d3.select(canvas).transition().duration(750).call(
          zoom.transform,
          d3.zoomIdentity.translate(width / 2, height / 2).scale(0.85)
        );
      };

      // Toggle Labels Button

      // --- Academic Trinity: Inlined PDF Viewer ---
      function openPdfModal(pdfUrl, title) {
        const modal = document.getElementById("pdfModal");
        const iframe = /** @type {HTMLIFrameElement | null} */ (document.getElementById("pdfModalFrame"));
        const titleEl = document.getElementById("pdfModalTitleText");
        const popout = /** @type {HTMLAnchorElement | null} */ (document.getElementById("pdfModalPopoutBtn"));
        if (!modal || !iframe) return;

        if (titleEl) titleEl.textContent = title || "Problem Sheet (PDF)";
        iframe.src = pdfUrl;
        if (popout) popout.href = pdfUrl;
        modal.style.display = "flex";
      }
      window.openPdfModal = openPdfModal;

      function closePdfModal() {
        const modal = document.getElementById("pdfModal");
        const iframe = /** @type {HTMLIFrameElement | null} */ (document.getElementById("pdfModalFrame"));
        if (modal) modal.style.display = "none";
        if (iframe) iframe.src = "";
      }
      window.closePdfModal = closePdfModal;
