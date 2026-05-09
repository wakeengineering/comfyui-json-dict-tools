import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

app.registerExtension({
  name: "comfyui-json-dict-tools.Nodes",
  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (nodeData.name === "JSONDICTExploder") {

      // --- 1. Dynamic Inputs Handling ---
      const onConnectionsChange = nodeType.prototype.onConnectionsChange;
      nodeType.prototype.onConnectionsChange = function (type, index, connected, link_info) {
        if (onConnectionsChange) onConnectionsChange.apply(this, arguments);
        
        if (type === 1) { // 1 = Input
          let emptyCount = 0;
          for (let i = this.inputs.length - 1; i >= 0; i--) {
            if (!this.inputs[i].link) emptyCount++;
            else break;
          }

          if (emptyCount === 0) {
            const nextNum = this.inputs.length + 1;
            this.addInput(`json_dict_data_${nextNum}`, "*");
          } else if (emptyCount > 1) {
            for (let i = this.inputs.length - 1; i > 0; i--) {
              if (!this.inputs[i].link && !this.inputs[i - 1].link) {
                this.removeInput(i);
              } else {
                break;
              }
            }
          }

          // Ensure names remain sequential for the Python kwargs merger
          for (let i = 0; i < this.inputs.length; i++) {
            this.inputs[i].name = `json_dict_data_${i + 1}`;
          }
          
          this.setSize(this.computeSize());
          app.graph.setDirtyCanvas(true, true);
        }
      };

      // --- 2. Clean Dynamic Outputs (Using addOutput / removeOutput) ---
      const onNodeCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        if (onNodeCreated) onNodeCreated.apply(this, arguments);
        
        // Remove all the excess outputs registered by the Python backend (50).
        // We will leave exactly 1 slot as a hint to the user.
        while (this.outputs && this.outputs.length > 1) {
            this.removeOutput(this.outputs.length - 1);
        }
        
        // Rename the sole remaining output to tell the user what to do
        if (this.outputs && this.outputs.length > 0) {
            this.outputs[0].name = "run_to_update...";
            this.outputs[0].label = "run_to_update...";
        }
        
        this.setSize(this.computeSize());
      };
    }

    if (nodeData.name === "JSONDICTSelector") {
      const onNodeCreated = nodeType.prototype.onNodeCreated;
      nodeType.prototype.onNodeCreated = function () {
        if (onNodeCreated) onNodeCreated.apply(this, arguments);

        const widgets = this.widgets || [];
        const keyWidgetIndex = widgets.findIndex((w) => w && w.name === "key_selector");
        if (keyWidgetIndex === -1) return;

        const existingWidget = widgets[keyWidgetIndex];
        const selectedValue = (existingWidget && existingWidget.value) ? String(existingWidget.value) : "";

        // Replace the default text widget with a combo widget fed by runtime keys.
        widgets.splice(keyWidgetIndex, 1);

        const comboWidget = this.addWidget(
          "combo",
          "key_selector",
          selectedValue,
          (value) => {
            comboWidget.value = value;
          },
          {
            values: selectedValue ? [selectedValue] : [""],
          }
        );

        if (selectedValue) {
          comboWidget.value = selectedValue;
        }

        this.setSize(this.computeSize());
      };
    }
  },

  async setup() {
    // --- 3. Live UI Updates from Python Execution ---
    api.addEventListener("JSONDICTExploder_keys", (event) => {
      const { node_id, keys } = event.detail;
      const node = app.graph.getNodeById(node_id);
      if (!node || node.type !== "JSONDICTExploder") return;

      // Fallback in case a completely empty dict gets passed
      const targetKeys = keys.length > 0 ? keys : ["empty_dict"];

      // A. Remove excess outputs if the new dict has fewer keys than before
      while (node.outputs && node.outputs.length > targetKeys.length) {
        const lastIdx = node.outputs.length - 1;
        // Important: disconnect any wires before removing to avoid ghost connections
        if (node.outputs[lastIdx].links && node.outputs[lastIdx].links.length > 0) {
            node.disconnectOutput(lastIdx);
        }
        node.removeOutput(lastIdx);
      }

      // B. Add new outputs if the new dict has more keys
      while (!node.outputs || node.outputs.length < targetKeys.length) {
        node.addOutput(`output_${node.outputs.length + 1}`, "*");
      }

      // C. Rename everything to match the live keys
      for (let i = 0; i < targetKeys.length; i++) {
        node.outputs[i].name = targetKeys[i];
        node.outputs[i].label = targetKeys[i];
      }
      
      node.setSize(node.computeSize());
      app.graph.setDirtyCanvas(true, true);
    });

    api.addEventListener("JSONDICTSelector_keys", (event) => {
      const { node_id, keys, selected } = event.detail;
      const node = app.graph.getNodeById(node_id);
      if (!node || node.type !== "JSONDICTSelector") return;

      const widgets = node.widgets || [];
      const keyWidget = widgets.find((w) => w && w.name === "key_selector");
      if (!keyWidget) return;

      const safeKeys = (Array.isArray(keys) && keys.length > 0)
        ? keys.map((k) => String(k))
        : [""];

      const currentValue = keyWidget.value ? String(keyWidget.value) : "";
      const preferred = selected ? String(selected) : currentValue;
      const nextValue = safeKeys.includes(preferred) ? preferred : safeKeys[0];

      if (!keyWidget.options) {
        keyWidget.options = {};
      }
      keyWidget.options.values = safeKeys;
      keyWidget.value = nextValue;

      // Keep serialized widget values in sync for prompt execution.
      if (Array.isArray(node.widgets_values)) {
        const widgetIndex = widgets.findIndex((w) => w && w.name === "key_selector");
        if (widgetIndex >= 0) {
          node.widgets_values[widgetIndex] = nextValue;
        }
      }

      node.setSize(node.computeSize());
      app.graph.setDirtyCanvas(true, true);
    });
  }
});