import { app } from "/scripts/app.js";

// Fetches image URLs from Booru via proxy, handling errors
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

// Registers BooruImageLoader extension with ComfyUI
app.registerExtension({
    name: "Alcatraz.BooruImageLoader.Client",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "BooruImageLoader") return;

        nodeType.prototype.onNodeCreated = function () {
            const node = this;
            console.log("Booru Loader: Configuring node widgets");

            // Retrieve widgets
            const widgets = {
                website: node.widgets.find(w => w.name === "website"),
                mode: node.widgets.find(w => w.name === "mode"),
                tags: node.widgets.find(w => w.name === "tags"),
                page: node.widgets.find(w => w.name === "page_number"),
                url: node.widgets.find(w => w.name === "selected_image_url")
            };

            if (Object.values(widgets).some(w => !w)) {
                console.error("Booru Loader: Missing required widgets");
                return;
            }

            // Configure URL dropdown
            widgets.url.type = "combo";
            let lastValidSelection = widgets.url.value || "Enter tags & page...";
            widgets.url.options = { values: [lastValidSelection] };
            let isUpdating = false; // Prevent recursive updates

            // Updates dropdown options based on widget inputs
            const updateDropdown = async () => {
                if (isUpdating) return; // Prevent recursive calls
                isUpdating = true;

                const { website, mode, tags, page, url } = widgets;
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
                url.value = url.options.values[0];
                node.setDirtyCanvas(true, true);

                const result = await fetchBooruImageUrls(tags.value, page.value, website.value);
                const newOptions = result.status === "success" && result.values.length
                    ? result.values.map(item => `${item.url}|${item.tags}`)
                    : result.values;
                const newValue = newOptions.includes(lastValidSelection) ? lastValidSelection : newOptions[0] || "Error: Unknown error";

                url.options.values = newOptions;
                url.value = newValue;
                lastValidSelection = newValue;
                node.setDirtyCanvas(true, true);
                console.log(`Booru Loader: ${result.status === "success" ? `Loaded ${newOptions.length} URLs` : result.values[0]}`);
                isUpdating = false;
            };

            // Debounced update trigger
            let debounceTimeout;
            const triggerUpdate = () => {
                clearTimeout(debounceTimeout);
                debounceTimeout = setTimeout(updateDropdown, 500);
            };

            // Attach callbacks to widgets
            widgets.url.callback = value => {
                if (!value.match(/^(Loading|Enter tags|Error|No results|Random mode)/)) lastValidSelection = value;
                node.setDirtyCanvas(true, true);
            };

            Object.entries(widgets).forEach(([key, widget]) => {
                if (key === "url") return;
                const originalCallback = widget.callback;
                widget.callback = value => {
                    if (key === "page") {
                        value = Number.isInteger(value) && value >= 0 ? value : (setTimeout(() => widget.value = 0, 0), 0);
                    }
                    if (originalCallback) originalCallback.call(widget, value);
                    triggerUpdate();
                };
            });

            console.log("Booru Loader: Initializing dropdown");
            updateDropdown();
        };

        // Clean up on node removal, avoiding recursive calls
        const originalOnRemoved = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            if (originalOnRemoved) originalOnRemoved.apply(this, arguments);
        };
    }
});