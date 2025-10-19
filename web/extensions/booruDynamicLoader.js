import { app } from "/scripts/app.js";

// Fetches image URLs from Booru via proxy, handling errors and timeouts
async function fetchBooruImageUrls(tags, page, website) {
    const trimmedTags = tags.trim();
    if (!trimmedTags) return { status: "info", values: ["Enter tags to search"] };

    const url = `/booru-proxy?tags=${encodeURIComponent(trimmedTags)}&page=${page}&website=${encodeURIComponent(website)}`;
    console.log(`Booru Loader: Fetching ${url}`);

    try {
        const response = await fetch(url, { signal: AbortSignal.timeout(25000) });
        if (!response.ok) {
            const errorText = await response.text();
            console.error(`Booru Loader: Proxy error ${response.status}: ${errorText}`);
            try {
                const errorJson = JSON.parse(errorText);
                if (errorJson?.values?.length) return { status: "error", values: [`API Error: ${errorJson.values.join(", ")}`] };
            } catch (_) {}
            return { status: "error", values: [`Proxy API Error ${response.status}`] };
        }

        const data = await response.json();
        if (!data?.status) {
            console.error("Booru Loader: Invalid data format:", data);
            return { status: "error", values: ["Invalid response format"] };
        }

        data.values = Array.isArray(data.values) ? data.values : data.status === "success" ? [] : [String(data.values)];
        return data;
    } catch (error) {
        console.error(`Booru Loader: Fetch error: ${error}`);
        return { status: "error", values: [error.name === "TimeoutError" ? "Request Timeout" : `Fetch failed (${error.message})`] };
    }
}

// Registers the extension for BooruImageLoader node
app.registerExtension({
    name: "Alcatraz.BooruImageLoader.Client",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "BooruImageLoader") return;

        nodeType.prototype.onNodeCreated = function () {
            const node = this;
            console.log("Booru Loader: Configuring widgets");

            // Retrieve core widgets (before replacement)
            let widgets = {
                website: node.widgets.find(w => w.name === "website"),
                mode: node.widgets.find(w => w.name === "mode"),
                tags: node.widgets.find(w => w.name === "tags"),
                page: node.widgets.find(w => w.name === "page_number"),
                save_locally: node.widgets.find(w => w.name === "save_locally")
            };

            if (Object.values(widgets).some(w => !w)) {
                console.error("Booru Loader: Missing core widgets");
                return;
            }

            // Replace STRING widget with COMBO for non-editable dropdown
            let urlWidget;
            const oldUrlWidget = node.widgets.find(w => w.name === "selected_image_url");
            if (oldUrlWidget) {
                const oldIndex = node.widgets.indexOf(oldUrlWidget);
                node.removeWidget(oldUrlWidget);  // Remove original STRING to avoid conflicts
                urlWidget = node.addWidget(
                    "combo",  // Creates a true <select> dropdown
                    "selected_image_url",
                    "Select URL...",  // Default value
                    "Selected Image URL",  // Label
                    { values: [] }  // Initial empty options; populated dynamically
                );
                // Re-insert at original position for layout consistency
                node.widgets.splice(oldIndex, 0, urlWidget);
                console.log("Booru Loader: Replaced STRING with COMBO dropdown widget");
            } else {
                console.error("Booru Loader: Could not find selected_image_url widget to replace");
                return;
            }

            // Update widgets object with new combo
            widgets.url = urlWidget;
            let lastValidSelection = urlWidget.value || "Select URL...";
            let isUpdating = false;

            // Dynamic save_path widget management (unchanged, as it works)
            let savePathWidget = null;
            const toggleSavePath = (enabled) => {
                const existingIndex = node.widgets.findIndex(w => w.name === "save_path");
                if (enabled && existingIndex === -1) {
                    // Add text widget for path input
                    savePathWidget = node.addWidget("text", "save_path", "booru_downloads", "Save Path", { 
                        multiline: false 
                    });
                    console.log("Booru Loader: Added save_path widget (node will expand)");
                } else if (!enabled && existingIndex !== -1) {
                    // Set empty value before removal to avoid serialization issues
                    if (savePathWidget) savePathWidget.value = "";
                    node.widgets.splice(existingIndex, 1);
                    savePathWidget = null;
                    console.log("Booru Loader: Removed save_path widget (node will shrink)");
                }
                node.setDirtyCanvas(true, true);  // Force node resize/refresh
            };

            // Initialize based on default save_locally
            toggleSavePath(widgets.save_locally.value);

            // Populate dropdown with fetched options (list of 'url|tags')
            const updateDropdown = async () => {
                if (isUpdating) return;
                isUpdating = true;

                const { mode, url } = widgets;
                if (mode.value === "random") {
                    url.options.values = ["Random mode: URL not applicable"];
                    url.value = url.options.values[0];
                    url.disabled = true;
                    node.setDirtyCanvas(true, true);
                    isUpdating = false;
                    return;
                }

                url.disabled = false;
                url.options.values = ["Loading URLs..."];
                url.value = "Loading URLs...";
                node.setDirtyCanvas(true, true);

                const { website, tags, page } = widgets;
                const result = await fetchBooruImageUrls(tags.value, page.value, website.value);
                const newOptions = result.status === "success" && result.values.length
                    ? result.values.map(item => `${item.url}|${item.tags}`)
                    : [result.values[0] || "No results found"];  // Fallback to single error/placeholder

                // Preserve last valid if possible, else first option
                const newValue = newOptions.includes(lastValidSelection) 
                    ? lastValidSelection 
                    : newOptions[0];

                url.options.values = newOptions;  // Update dropdown options
                url.value = newValue;
                lastValidSelection = newValue;
                node.setDirtyCanvas(true, true);
                console.log(`Booru Loader: Dropdown updated with ${newOptions.length} options (${result.status})`);
                isUpdating = false;
            };

            // Debounced trigger for changes (e.g., tags/page/website)
            let debounceTimeout;
            const triggerUpdate = () => {
                clearTimeout(debounceTimeout);
                debounceTimeout = setTimeout(updateDropdown, 500);
            };

            // URL callback: Update on selection change (non-editable, so only triggers on select)
            widgets.url.callback = (value) => {
                if (!value.match(/^(Loading|Select|Error|No results|Random mode)/i)) {
                    lastValidSelection = value;
                    console.log(`Booru Loader: Selected URL: ${value.substring(0, 50)}...`);
                }
                node.setDirtyCanvas(true, true);
            };

            // Callbacks for other widgets
            Object.entries(widgets).forEach(([key, widget]) => {
                if (key === "url") return;
                const original = widget.callback;
                widget.callback = (value) => {
                    if (key === "page") {
                        value = Math.max(0, parseInt(value) || 0);
                        widget.value = value;
                    }
                    if (key === "save_locally") {
                        toggleSavePath(value);
                        // Don't trigger dropdown update on save toggle
                        return;
                    }
                    if (original) original.call(widget, value);
                    triggerUpdate();  // Refresh dropdown on relevant changes
                };
            });

            // Initial population if tags have default value
            if (widgets.tags.value.trim()) {
                setTimeout(triggerUpdate, 100);  // Slight delay for node stability
            }

            console.log("Booru Loader: Initialization complete. Enter tags to populate dropdown.");
        };

        // Cleanup dynamic widget on node removal
        const originalOnRemoved = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            const saveIndex = this.widgets?.findIndex(w => w.name === "save_path");
            if (saveIndex !== -1) {
                this.widgets.splice(saveIndex, 1);
            }
            if (originalOnRemoved) originalOnRemoved.apply(this, arguments);
        };
    }
});