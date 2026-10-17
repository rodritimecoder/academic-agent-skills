      const toggleLabelsBtn = document.getElementById("toggleLabelsBtn");
      toggleLabelsBtn.onclick = () => {
        showLabels = !showLabels;
        toggleLabelsBtn.classList.toggle("active", showLabels);
        requestRender();
      };

      // Settings Popover Toggle
      const settingsBtn = document.getElementById("settingsBtn");
      const settingsPopover = document.getElementById("settingsPopover");
      settingsBtn.onclick = () => {
        settingsPopover.classList.toggle("open");
      };

      // Physics Sliders
      document.getElementById("sliderCharge").oninput = e => {
        const val = +e.target.value;
        document.getElementById("valCharge").textContent = val;
        simulation.force("charge").strength(val);
        simulation.alpha(0.3).restart();
      };

      document.getElementById("sliderLink").oninput = e => {
        const val = +e.target.value;
        document.getElementById("valLink").textContent = val;
        simulation.force("link").distance(val);
        simulation.alpha(0.3).restart();
      };

      document.getElementById("sliderCluster").oninput = e => {
        clusterStrength = +e.target.value;
        document.getElementById("valCluster").textContent = clusterStrength;
        simulation.force("clusterX").strength(clusterStrength);
        simulation.force("clusterY").strength(clusterStrength);
        simulation.alpha(0.3).restart();
      };

      // Aesthetics Toggles
      const toggleGlowRow = document.getElementById("toggleGlowRow");
      toggleGlowRow.onclick = () => {
        enableHaloBloom = !enableHaloBloom;
        toggleGlowRow.classList.toggle("toggle-active", enableHaloBloom);
        requestRender();
      };

      const togglePulsesRow = document.getElementById("togglePulsesRow");
      togglePulsesRow.onclick = () => {
        enablePulses = !enablePulses;
        togglePulsesRow.classList.toggle("toggle-active", enablePulses);
        requestRender();
      };

      // Search Filter Input
      const searchInput = document.getElementById("searchInput");
      searchInput.oninput = e => {
        searchQuery = e.target.value.toLowerCase().trim();
        if (searchQuery) {
          const match = nodes.find(n => n.label.toLowerCase().includes(searchQuery));
          if (match) {
            d3.select(canvas).transition().duration(500).call(
              zoom.transform,
              d3.zoomIdentity.translate(width / 2, height / 2).scale(1.2).translate(-match.x, -match.y)
            );
          }
        }
        requestRender();
      };


      // Initialize view mode state after all functions and models are defined
      setViewMode(currentViewMode, false);

      // Expose for testing and external inspection
      window.__graph = {
        nodes,
        selectNode,
        simulation,
        requestRender,
        setViewMode,
                openCornellModal,
        openDigUpModal,
        closeDigUpModal,
        performDigUpSearch,
        runDigUpTest: () => {
          const hasModal = !!document.getElementById("digupModal");
          const hasCorpus = Array.isArray(digupSlideCorpus) && digupSlideCorpus.length > 0;
          return { passed: hasModal && hasCorpus, slideCount: digupSlideCorpus.length };
        },
        openAnkiModal,
        startAnkiSession,
        renderKanbanBoard,
        filterKanbanCourse
      };
    });
