from llama_cpp import llama_grammar
from llama_cpp import llama_grammar
import json
from typing import Optional

def gbnf_char(char: str):
    """
    Escapes a character for use in a GBNF rule.
    """
    specials = ['\\', '"', '[', ']', '{', '}', '(', ')', '<', '>', '|', '^', '$', '*', '+', '?', '.']
    for special in specials:
        char = char.replace(special, "\\" + special)
    return char
def gbnf_literal(str: str):
    """
    Returns the string as a GBNF literal.
    """
    return '"' + str.replace('"', '\\"') + '"'

def gbnf_sanitize(str: str):
    """
    Sanitizes a string for use in as GBNF rule name.
    Regex Replace all characters that are not alphanumeric or a hyphen with a hyphen.
    """
    return ''.join(c if c.isalnum() or c == '-' else '-' for c in str)

def gbnf_or(options: list[str]):
    """
    Returns a GBNF rule that matches any of the arguments.
    """
    return '( ' + ' | '.join(['( '+o+' )' for o in options]) + ' )'

def gbnf_not(str: str):
    """
    Returns a GBNF rule that matches any sequence of characters that is not `str`.
    """
    rules = []
    prefix = ""
    for i in range(len(str)):
        rules.append(f'({gbnf_literal(prefix)} [^{gbnf_char(str[i])}])')
        prefix += str[i]
    return '(' + ' | '.join(rules) + ')'    



def functions_to_gbnf(functions: list[dict[str, any]]):
    prop_order = []
    prop_order = {name: idx for idx, name in enumerate(prop_order)}
    converter = llama_grammar.SchemaConverter(
        prop_order=prop_order, allow_fetch=False, dotall=False, raw_pattern=False
    )

    converter.visit({}, 'object') # guarantee that object is defined
    for function in functions:
        name = gbnf_sanitize(function["name"])
        parameters = function["parameters"]
        schema = converter.resolve_refs(parameters, "stdin")
        converter.visit(schema, name+'-parameters')
    
    return "\n".join(
        f"{name} ::= {rule}"
        for name, rule in sorted(converter._rules.items(), key=lambda kv: kv[0])
    )
