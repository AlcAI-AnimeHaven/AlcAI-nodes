import torch

class AnyType(str):
    """A class that always equals any value in comparisons."""
    def __eq__(self, _): return True
    def __ne__(self, _): return False

any = AnyType("*")

class LogicGatesForBoolean:
    """A ComfyUI node for logical operations (AND, OR, XOR, NAND, NOR, XNOR) on boolean inputs."""
    
    @classmethod
    def INPUT_TYPES(cls):
        """Define input types: two booleans and a logic mode."""
        return {
            "required": {
                "boolean_a": ("BOOLEAN", {"default": False, "label_on": "True", "label_off": "False"}),
                "boolean_b": ("BOOLEAN", {"default": False, "label_on": "True", "label_off": "False"}),
                "mode": (["AND", "OR", "XOR", "NAND", "NOR", "XNOR"],)
            }
        }

    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("boolean_out",)
    FUNCTION = "evaluate_gate"
    CATEGORY = "Logic Gates"

    def evaluate_gate(self, boolean_a, boolean_b, mode):
        """Evaluate the logical operation based on mode.

        Args:
            boolean_a (bool): First boolean input.
            boolean_b (bool): Second boolean input (ignored for NOT).
            mode (str): Logical operation to perform.

        Returns:
            tuple: Single boolean result.
        """
        operations = {
            "AND": boolean_a and boolean_b,
            "OR": boolean_a or boolean_b,
            "XOR": boolean_a ^ boolean_b,
            "NAND": not (boolean_a and boolean_b),
            "NOR": not (boolean_a or boolean_b),
            "XNOR": boolean_a == boolean_b
        }
        result = operations[mode]
        print(f"LogicGate: {boolean_a} {mode} {boolean_b} = {result}")
        return (result,)

class LogicGateForAnyValue:
    """A ComfyUI node that passes truthy values or None for falsy values."""
    
    @classmethod
    def INPUT_TYPES(cls):
        """Define input type: any value."""
        return {"required": {"value": (any, {})}}

    RETURN_TYPES = (any, "BOOLEAN")
    RETURN_NAMES = ("any", "boolean")
    FUNCTION = "evaluate_condition"
    CATEGORY = "Logic"

    def evaluate_condition(self, value):
        """Check if value is truthy, return value or None.

        Args:
            value (any): Input value of any type.

        Returns:
            tuple: (value if truthy else None, is_truthy).
        """
        is_truthy = value.numel() > 0 if isinstance(value, torch.Tensor) else bool(value)
        result = value if is_truthy else None
        print(f"PassValueIfTruthy: Input '{value}' (type: {type(value)}) is {'truthy' if is_truthy else 'falsy'}. Output: {result}")
        return (result, is_truthy)
    
class LogicGateSwitchForAnyValue:
    """A ComfyUI node that passes truthy values or None for falsy values."""
    
    @classmethod
    def INPUT_TYPES(cls):
        """Define input type: any value."""
        return {"required": {"value_if_true": (any, {}),"value_if_false": (any, {}),"boolean": ("BOOLEAN", {"default": False, "label_on": "True", "label_off": "False"})}}

    RETURN_TYPES = (any,)
    RETURN_NAMES = ("any",)
    FUNCTION = "evaluate_condition"
    CATEGORY = "Logic"

    def evaluate_condition(self, value_if_true, value_if_false, boolean):
        if value_if_true and value_if_false:
            if boolean:
                return (value_if_true,)
            else:
                return(value_if_false,)