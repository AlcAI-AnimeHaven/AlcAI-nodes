import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

// Utility to debounce a function
const debounce = (func, wait) => {
  let timeout;
  return (...args) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
};

app.registerExtension({
  name: "Comfy.ImageLoaderEnhanced",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "ImageLoaderEnhanced") return;
    console.log("[RIL Enhanced] Patching node:", nodeData.name);

    // Fetch directories from API
    async function fetchDirectories() {
      try {
        const res = await api.fetchApi("/ril/get_directories");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const directories = await res.json();
        console.debug(`[RIL Enhanced] Fetched ${directories.length} directories`);
        return directories.length ? directories : ["[INPUT]"];
      } catch (err) {
        console.error("[RIL Enhanced] fetchDirectories error:", err);
        return ["[INPUT]"];
      }
    }

    // Fetch filenames for a directory
    async function fetchFilenames(directory = "[INPUT]") {
      try {
        const params = new URLSearchParams({ directory });
        const res = await api.fetchApi(`/ril/get_filenames?${params}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const filenames = Array.isArray(data) ? data : (data.filenames || []);
        const subfolder = data.subfolder ?? "";
        const type = data.type ?? "input";
        console.debug(`[RIL Enhanced] Fetched ${filenames.length} filenames for ${directory} (subfolder='${subfolder}', type='${type}')`);
        return {
          filenames: filenames.length ? filenames : [""],
          subfolder,
          type
        };
      } catch (err) {
        console.error("[RIL Enhanced] fetchFilenames error:", err);
        return { filenames: [""], subfolder: "", type: "input" };
      }
    }

    // Toggle filename widget visibility based on mode
    function setWidgetVisibility(node) {
      const modeWidget = node.widgets?.find(w => w.name === "mode");
      const filenameWidget = node.widgets?.find(w => w.name === "filename");
      if (!modeWidget || !filenameWidget?.element) {
        console.warn("[RIL Enhanced] Widgets not ready, retrying...");
        setTimeout(() => setWidgetVisibility(node), 100);
        return;
      }

      const isRandom = modeWidget.value === "Random";
      filenameWidget.disabled = isRandom;
      filenameWidget.element.style.opacity = isRandom ? "0.5" : "1";
      filenameWidget.element.style.pointerEvents = isRandom ? "none" : "auto";
      node.setDirtyCanvas(true, true);
    }

    // Create/update inline preview under filename widget
    function setPreview(node) {
      const filenameWidget = node.widgets?.find(w => w.name === "filename");
      if (!filenameWidget || !filenameWidget.element) return;

      const container = filenameWidget.element;
      let img = container.querySelector("img.__ril_preview");
      if (!img) {
        img = document.createElement("img");
        img.className = "__ril_preview";
        img.style.display = "block";
        img.style.marginTop = "6px";
        img.style.maxWidth = "256px";
        img.style.maxHeight = "256px";
        img.style.objectFit = "contain";
        container.appendChild(img);
      }

      const filename = filenameWidget.value;
      const effectiveMeta = node.__ril_preview_meta || node.__ril_meta || { subfolder: "", type: "input" };
      if (!filename) {
        img.src = "";
        img.style.display = "none";
        return;
      }

      const params = new URLSearchParams({ filename, subfolder: effectiveMeta.subfolder || "", type: effectiveMeta.type || "input" });
      img.src = `/view?${params.toString()}`;
      img.style.display = "block";
    }

    // Ensure previewable copy exists in INPUT root for selected image
    async function ensureInputPreview(node) {
      try {
        const filenameWidget = node.widgets?.find(w => w.name === "filename");
        if (!filenameWidget) return;
        const filename = filenameWidget.value;
        const meta = node.__ril_meta || { subfolder: "", type: "input" };
        if (!filename) return;

        const res = await api.fetchApi(`/ril/ensure_input_preview`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filename, subfolder: meta.subfolder || "", type: meta.type || "input" })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        // After ensuring, prefer preview from INPUT root to avoid subfolder dependency
        node.__ril_preview_meta = { subfolder: "", type: "input" };
      } catch (err) {
        console.warn("[RIL Enhanced] ensureInputPreview failed, falling back to original location", err);
        node.__ril_preview_meta = null;
      }
    }

    // Update directory and filename widgets
    async function updateWidgets(node) {
      const widgets = {
        directory: node.widgets?.find(w => w.name === "directory"),
        filename: node.widgets?.find(w => w.name === "filename"),
        mode: node.widgets?.find(w => w.name === "mode")
      };
      if (!widgets.directory || !widgets.filename || !widgets.mode) {
        console.error("[RIL Enhanced] Missing required widgets");
        return;
      }

      // Update directories
      const directories = await fetchDirectories();
      widgets.directory.options.values = directories;
      if (!directories.includes(widgets.directory.value)) {
        widgets.directory.value = "[INPUT]";
      }

      // Update filenames
      const { filenames, subfolder, type } = await fetchFilenames(widgets.directory.value);
      widgets.filename.options.values = filenames;
      widgets.filename.value = filenames.includes(widgets.filename.value) 
        ? widgets.filename.value 
        : filenames[0];

      // Save meta for preview URL building
      node.__ril_meta = { subfolder, type };
      node.__ril_preview_meta = null; // reset override until ensured

      setWidgetVisibility(node);
      await ensureInputPreview(node);
      setPreview(node);
    }

    // Wrap widget callback to trigger updates
    function wrapCallback(widget, originalCallback, node, updateFn) {
      widget.callback = value => {
        console.debug(`[RIL Enhanced] ${widget.name} changed:`, value);
        if (originalCallback) originalCallback.call(widget, value);
        if (widget.name === "filename" && node.graph) {
          node.graph.setDirtyCanvas(true, true);
          node.graph.afterChange();
        }
        if (widget.name === "filename") {
          (async () => {
            await ensureInputPreview(node);
            setPreview(node);
          })();
        }
        updateFn();
      };
    }

    nodeType.prototype.onNodeCreated = function () {
      console.log("[RIL Enhanced] Node created, ID:", this.id);
      const node = this;
      const widgets = {
        directory: node.widgets?.find(w => w.name === "directory"),
        filename: node.widgets?.find(w => w.name === "filename"),
        mode: node.widgets?.find(w => w.name === "mode")
      };
      if (!widgets.directory || !widgets.filename || !widgets.mode) {
        console.error("[RIL Enhanced] Missing widgets on node creation");
        return;
      }

      // Ensure directory widget is a combo box
      widgets.directory.type = "combo";
      widgets.directory.options = widgets.directory.options || {};

      // Debounced update handler
      const handleUpdate = debounce(() => updateWidgets(node), 250);

      // Attach callbacks
      Object.values(widgets).forEach(widget => 
        wrapCallback(widget, widget.callback, node, handleUpdate)
      );

      updateWidgets(node);
    };

    // Update visibility and widgets after drawing
    const onDrawn = nodeType.prototype.onDrawn;
    nodeType.prototype.onDrawn = function () {
      if (onDrawn) onDrawn.apply(this, arguments);
      console.debug("[RIL Enhanced] Node drawn, ID:", this.id);
      setWidgetVisibility(this);
      updateWidgets(this);
    };

    console.log("[RIL Enhanced] Node patching complete");
  }
});

console.log("[RIL Enhanced] Extension registered");