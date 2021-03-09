from pathlib import Path
import gzip

def listing(dirs):
    res = {}
    for d in dirs:
        for manpage in d.glob("**/*"):
            if manpage.is_file():
                split_by_dot = manpage.name.split(".")
                compression = None
                if split_by_dot[-1] == "gz":
                    compression = "gz"
                    split_by_dot.pop()
                section = split_by_dot[-1]
                split_by_dot.pop()
                manpage_name = ".".join(split_by_dot)
                if manpage_name in res:
                    res[manpage_name][section] = (manpage, compression)
                else:
                    res[manpage_name] = { section: (manpage, compression) }

    return res

manpaths = ["/usr/share/man/man" + str(x) for x in range(1, 9)]
man_listings = listing([Path(p) for p in manpaths])

def read_manpage(name, section=None):
    pages_by_sections = man_listings[name]
    manpage_path = None
    if section == None:
        for k, v in pages_by_sections.items():
            manpage_path = v
            break
    else:
        manpage_path = pages_by_sections[section]

    # read the path
    my_file = None
    if manpage_path[1] == "gz":
        my_file = gzip.open(manpage_path[0])
    else:
        my_file = open(manpage_path[0])

    with my_file:
        lines = [x.decode("utf-8") for x in my_file.readlines()]
        return lines

# Encode manpage as a whatsapp message
def whatsapp_encoding(lines):
    lines = [x.replace("*", "∗").replace("_", "⎽") for x in lines if not x.startswith(".\\\"")]
    result = ""

    def add_formatting(txt, withchar):
        pretrailing_spaces = 0
        trailing_spaces = 0
        while txt.startswith(" "):
            pretrailing_spaces += 1
            txt = txt[1:]
        while txt.endswith(" "):
            trailing_spaces += 1
            txt = txt[:-1]
        return " " + (" " * pretrailing_spaces) + withchar + txt + withchar + (" " * trailing_spaces)
    
    for line in lines:
        line = line[:line.find("\n")]
        if line.startswith("."):
            if line.startswith(".TH"):
                # header
                parts = line.split()[1:]
                manpage_name = parts[0]
                manpage_part = parts[1]
                result += "```" + manpage_name + "(" + manpage_part + ")" +  "```\n"
            elif line.startswith(".TP"):
                result += "\n"
            elif line.startswith(".SH"):
                # section
                result += "\n*---" + line[4:] + "---*\n\n"
            elif line.startswith(".BR"):
                # reference bold
                result += add_formatting(line[4:], "*")
            elif line.startswith(".B"):
                # bold
                result += add_formatting(line[3:], "*")
            elif line.startswith(".I"):
                # italics
                result += add_formatting(line[3:], "_")
            elif line.startswith(".PP"):
                # paragraph
                result += "\n\n"
            else:
                result += "\n" + line + "\n"
        else:
            result += " " + line
    return result

print(whatsapp_encoding(read_manpage("fdopen")))
#print("".join(read_manpage("fdopen")))
