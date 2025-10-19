import { app } from "/scripts/app.js";

app.registerExtension({
    name: "LoraLoaderAndKeywords.UI.Final",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name === "LoraLoaderAndKeywords") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            
            nodeType.prototype.onNodeCreated = function () {
                onNodeCreated?.apply(this, arguments);

                const node = this; // Garder une référence au node
                const loraNameWidget = node.widgets.find(w => w.name === "lora_name");
                
                // --- SOLUTION ROBUSTE : Remplacer le widget ---

                // 1. Trouver le widget 'STRING' original que nous voulons remplacer.
                const originalTriggerWidget = node.widgets.find(w => w.name === "trigger_word");
                
                // 2. Garder en mémoire sa valeur actuelle (très important pour le chargement de workflows).
                const initialValue = originalTriggerWidget.value || "";
                
                // 3. Créer un NOUVEAU widget de type "combo".
                //    La méthode `addWidget` est l'API officielle de ComfyUI pour cela.
                const comboWidget = node.addWidget(
                    "combo",                // type
                    "trigger_word",         // name (doit être le même)
                    initialValue,           // valeur initiale
                    () => {},               // callback (on le redéfinira plus tard)
                    { values: [initialValue] } // options
                );
                
                // 4. Supprimer l'ancien widget texte de la liste des widgets.
                node.widgets.splice(node.widgets.indexOf(originalTriggerWidget), 1);

                // --- Le widget est maintenant un vrai "combo". On peut y attacher notre logique. ---

                let isUpdating = false;

                const updateTriggerWords = async () => {
                    if (isUpdating) return;
                    isUpdating = true;

                    const loraName = loraNameWidget.value;
                    const lastValidValue = comboWidget.value; // Utiliser la valeur actuelle du combo

                    if (!loraName || loraName === "None") {
                        comboWidget.options.values = [""];
                        comboWidget.value = "";
                        isUpdating = false;
                        return;
                    }

                    try {
                        comboWidget.value = "Loading...";
                        const response = await fetch(`/lora_keywords/${encodeURIComponent(loraName)}`);
                        if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);
                        const keywords = await response.json();
                        
                        let newOptions;
                        if (Array.isArray(keywords) && keywords.length > 0) {
                            newOptions = keywords;
                        } else {
                            newOptions = ["(none)"];
                        }
                        
                        comboWidget.options.values = newOptions;

                        // Rétablir la valeur si elle existe toujours, sinon prendre la première.
                        if (newOptions.includes(lastValidValue)) {
                            comboWidget.value = lastValidValue;
                        } else {
                            comboWidget.value = newOptions[0] || "";
                        }

                    } catch (error) {
                        console.error(`Failed to fetch keywords for ${loraName}:`, error);
                        const errorMsg = "(API Error)";
                        comboWidget.options.values = [errorMsg];
                        comboWidget.value = errorMsg;
                    } finally {
                        isUpdating = false;
                        app.graph.setDirtyCanvas(true, true);
                    }
                };
                
                // Attacher le callback au widget LoRA pour déclencher la mise à jour.
                loraNameWidget.callback = () => {
                    updateTriggerWords();
                };

                // Lancer la première mise à jour.
                setTimeout(updateTriggerWords, 10);
            };
        }
    },
});