from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *
from PySide2.QtUiTools import *
import re
import hou
from pprint import pprint

def assign_material(run=False):
    
    # Get current network editor
    pane = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    if not pane:
        hou.ui.displayMessage("No Network Editor is currently open.")
        return None

    current_net = pane.pwd() # Get the current network path (the network the user has open)

    # Find all materialassign and matlibrary nodes in this network
    assign_mat = [n for n in current_net.allSubChildren() if n.type().name() == "assignmaterial"]
    mat_library = [n for n in current_net.allSubChildren() if n.type().name() == "materiallibrary"]
    
    if not assign_mat:
        hou.ui.displayMessage("No Assign Material nodes found in the current network")
        return None
    if not mat_library:
        hou.ui.displayMessage("No Material Library nodes found in the current network")
        return None

    # Get selected nodes
    selected = hou.selectedNodes()
    # if nodes are not selected
    if len(selected) != 2:
        hou.ui.displayMessage("Select Material Library AND Assign Material nodes")
        return

    # Identify nodes
    mat_library = assign_mat = None
    for node in selected:
        tname = node.type().name().lower()
        if tname == "materiallibrary":
            mat_library = node
        elif tname == "assignmaterial":
            assign_mat = node

    # Validate that we found both types
    if not mat_library or not assign_mat:
        hou.ui.displayMessage("Selection must contain one Material Library node and one Assign Material node.")
        return

    # Check connection
    connected = False # It starts as False, meaning we have not found a connection yet.
    for connection in assign_mat.inputConnections():
        if connection.inputNode() == mat_library:
            connected = True
            break

    # if selected nodes are not connected
    if not connected:
        
        button_choice = hou.ui.displayMessage("Nodes are not connected. Do you want me to connect them?", # ask user if he wants to connect selected nodes
            buttons = ("Yes", "No"),
            default_choice = 0,
            close_choice = 1
        )

    # connect nodes automatically
        if button_choice == 0:
            try:
                assign_mat.setNextInput(mat_library)
            except hou.InvalidInput:
                    hou.ui.displayMessage("Invalid connection!")
            except hou.OperationFailed:
                    hou.ui.displayMessage("Operation failed!")   
                    return

    # Gather materials from the library
    material_children = mat_library.children()
    if not material_children:
        hou.ui.displayMessage("Material Library contains no materials.") 
        return

    # list of tuples
    #materials_info = [(m.name(), m.path(), m) for m in material_children]

    # list of tuples
    materials_info = []
    for material_node in material_children:
        material_name = material_node.name()
        material_path = material_node.path()
        materials_info.append((material_name, material_path, material_node))

    # Fetch USD stage from Assign Material input
    input_node = mat_library.inputs()[0] if mat_library.inputs() else None
    if not input_node:
        hou.ui.displayMessage("Material Library node has no input connected")
        return

    stage = input_node.stage()
    if not stage:
        hou.ui.displayMessage("Could not access USD stage from input node")
        return

    # Collect assignable primitives
    geo_prims = [p for p in stage.Traverse() if p.GetTypeName() in ("Mesh", "PointInstancer", "Scope")]

    if not geo_prims:
        hou.ui.displayMessage("No assignable primitives found in the USD stage")
        return

    # Get multiparm controller
    material_parm = assign_mat.parm("nummaterials")
    if not material_parm:
        hou.ui.displayMessage("Could not find 'nummaterials' parameter on Assign Material node")
        return

    # Clear existing multiparm instances
    material_parm.set(0)

    #list of unmatched primitives/materials
    unmatched_prims = [] 
    unmatched_mats = []

    for node in material_children:
        unmatched_mats.append(node.name())

    # Assign materials based on primitive names
    for prim in geo_prims:

        prim_name = prim.GetName()
        
        condition = False
        match = None
        for info in materials_info:
            mat_name = info[0].split("_mtl")[0]
            if re.search(mat_name, prim_name):
                condition = True
                match = info[0]
                break

        if condition:
            material_path = "/".join(["/materials", match])
            material_parm.insertMultiParmInstance(material_parm.eval()) # Append new multiparm instance at the end
            instance_index = material_parm.eval()  # new instance index

            group_parm = assign_mat.parm(f"primpattern{instance_index}")
            shop_parm = assign_mat.parm(f"matspecpath{instance_index}")

            group_parm.set(str(prim.GetPath()))
            shop_parm.set(material_path)
            if match in unmatched_mats:
                unmatched_mats.remove(match)
        else:
            unmatched_prims.append(prim_name)
    
    unmatched = ""

    if unmatched_prims:
        #hou.ui.displayMessage("Some primitives/materials did not match any material:\n" + "\n".join(unmatched_prims))
        unmatched += "Materials assigned! \nBut some primitives did not match any material:\n" + "\n".join(unmatched_prims)

    if unmatched_mats:
        unmatched += "Materials assigned! \nBut some materials did not match any primitive:\n" + "\n".join(unmatched_mats)

    if unmatched == "":
        hou.ui.displayMessage("All materials assigned successfully!")
    else:
        hou.ui.displayMessage(unmatched)


def onCreateInterface():
    #Get Houdini main Qt window (parent)
    main_window = hou.ui.mainQtWindow()

    #Path to my ui
    ui_path = r'P:\all_work\userNames\ds24abc\Python_tool\UI_Tool_window.ui'

    #Make sure the file exists
    file = QFile(ui_path)
    if not file.exists():
        hou.ui.displayMessage(f"UI file not found: \n{ui_path}", severity = hou.severityType.Error)
        return None

    #Load the Ui
    file.open(QFile.ReadOnly)
    loader = QUiLoader()
    ui = loader.load(file, main_window)
    file.close()

    #Check if load failed
    if ui is None:
        hou.ui.displayMessage("Failed to load UI file (check for bad widgets or missing slots).", severity = hou.severityType.Error)

    #rename the window
    ui.setObjectName("assign_material_window")
    ui.setWindowTitle("Assign Materials")

    # connect buttons safely
    if hasattr(ui, "std_push_button"):
        ui.std_push_button.clicked.connect(assign_material)
    else:
        hou.ui.displayMessage("UI missing 'std_push_button'", severity = hou.severityType.Warning)

    # make it proper floating Houdini window
    ui.setWindowFlags(Qt.Window)
    ui.show()

    return ui

global ui_instance 
ui_instance = onCreateInterface()