// AnimeCharacterSelector.js
import { app } from "/scripts/app.js";

app.registerExtension({
    name: "Mira.AnimeCharacterSelector.API.v1",
    dataLoadedPromise: null,
    characterData: null,
    loadingError: false,

    setup() {
        console.log("AnimeCharacterSelector JS: Initializing API data load...");
        this.dataLoadedPromise = fetch(`/mira/get_character_data?t=${Date.now()}`)
            .then(response => {
                if (!response.ok) throw new Error(`API error: ${response.status} ${response.statusText}`);
                return response.json();
            })
            .then(data => {
                if (!data || typeof data !== "object" || !Object.keys(data).length) {
                    throw new Error("API returned invalid or empty data.");
                }
                this.characterData = data;
                this.loadingError = false;
                console.log("AnimeCharacterSelector JS: Character data loaded.");
            })
            .catch(error => {
                console.error("AnimeCharacterSelector JS: Failed to load API data:", error);
                this.characterData = { Error: ["random", `API Load Failed: ${error.message}`] };
                this.loadingError = true;
                throw error;
            });
    },

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "AnimeCharacterSelector") return;

        const self = this;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = async function () {
            if (onNodeCreated) onNodeCreated.apply(this, arguments);

            console.log(`ACS JS: Node ${this.id} created. Waiting for API data...`);
            try {
                await self.dataLoadedPromise;
                console.log(`ACS JS: API data ready for node ${this.id}.`);
            } catch (error) {
                console.error(`ACS JS: Error state for node ${this.id}.`);
            }

            const categoryWidget = this.widgets.find(w => w.name === "Characters_from");
            const characterWidget = this.widgets.find(w => w.name === "character");
            if (!categoryWidget || !characterWidget) {
                console.error(`ACS JS: Node ${this.id}: Missing required widgets.`);
                return;
            }

            const populateCategories = () => {
                const data = self.characterData || {};
                const categories = Object.keys(data).length ? Object.keys(data) : ["Error"];
                const currentCategory = categoryWidget.value;
                categoryWidget.options.values = categories;

                const selectEl = categoryWidget.inputEl;
                if (selectEl?.nodeName === "SELECT") {
                    selectEl.innerHTML = categories.map(cat => `<option value="${cat}">${cat}</option>`).join("");
                    categoryWidget.value = selectEl.value = categories.includes(currentCategory) ? currentCategory : categories[0];
                } else {
                    categoryWidget.value = !categories.includes(currentCategory) ? categories[0] : currentCategory;
                    console.warn(`ACS JS: Node ${this.id}: Category SELECT element not found.`);
                }

                if (categoryWidget.value !== currentCategory && categoryWidget.callback) {
                    categoryWidget.callback(categoryWidget.value);
                }
            };

            const updateCharacterOptions = () => {
                const selectedCategory = categoryWidget.value;
                const currentCharacter = characterWidget.value;
                const characters = (self.characterData?.[selectedCategory] || ["random", "Error: Invalid Category"]);
                characterWidget.options.values = characters;

                const selectEl = characterWidget.inputEl;
                if (selectEl?.nodeName === "SELECT") {
                    selectEl.innerHTML = characters.map(char => `<option value="${char}">${char}</option>`).join("");
                    characterWidget.value = selectEl.value = characters.includes(currentCharacter) ? currentCharacter : characters[0];
                } else {
                    characterWidget.value = characters.includes(currentCharacter) ? currentCharacter : characters[0];
                    console.warn(`ACS JS: Node ${this.id}: Character SELECT element not found.`);
                }

                if (characterWidget.value !== currentCharacter && characterWidget.callback) {
                    characterWidget.callback(characterWidget.value);
                }

                characterWidget.disabled = selectedCategory === "RANDOM";
                app.graph.setDirtyCanvas(true, true);
            };

            populateCategories();
            const originalCallback = categoryWidget.callback;
            categoryWidget.callback = value => {
                if (originalCallback) originalCallback.call(categoryWidget, value);
                updateCharacterOptions();
            };
            updateCharacterOptions();

            console.log(`ACS JS: Node ${this.id} setup complete.`);
        };
    }
});