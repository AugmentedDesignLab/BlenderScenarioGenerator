# BlenderScenarioGenerator
Generate roads and scenarios for testing autonomous vehicles in simulation using Blender python scripting. Output will be an OpenDRIVE file, an OpenSCENARIO file and an FBX file. All three of these formats can be imported into autonomous vehicle simulators such as CARLA. 

## Getting started
* First, [download and install Blender](https://www.blender.org/download/). This is a 3D modeling tool. It has a [Python API](https://docs.blender.org/api/current/info_overview.html). This repository contains python scripts that make use of this API for generating roads.
* Add the [Blender installation directory](https://docs.blender.org/manual/en/latest/advanced/command_line/launch/index.html) to the environment variable such that the command *blender* can be accessed from the command line. [Here](https://docs.blender.org/manual/en/latest/advanced/command_line/launch/macos.html) are the instructions for doing so on MacOS and [here](https://docs.blender.org/manual/en/latest/advanced/command_line/launch/windows.html) are the instructions for doing so on Windows.
* For the python installation in Blender, install the python package *scenariogeneration.* This package contains autonomous vehicle scenario generation scripts, particularly in the OpenDRIVE and OpenSCENARIO formats. This can be done using the command 
```
"<path-to-blender-python-directory>/bin/python" -m pip install scenariogeneration --target "<path-to-blender-python-directory>\lib\site-packages
``` 
This will ensure the package is installed and accessible by the Blender python installation. 
* Clone this repository and change directory to the project root. 
* Run the python script *road_base.py* using the **Blender python only**. This will *register* the `pr` (procedural roads) set of operations under `bpy.ops` The command for running this script would be 
```
blender --python road_base.py
```
* From within the Blender python console, run 
```
bpy.ops.pr.road()
```

This should generate a road in the 3D viewport. You can do the same for any other Blender operator written.
* Since we are using the Blender python, imports need to be done this way:
```
import os
import sys
import imp

#Add this directory to path so that the files here can be found by Blender python

dir = os.path.dirname(bpy.data.filepath)
if not dir in sys.path:
    sys.path.append(dir)

# Below this, import all the python scripts in this project that are needed. Reload if the module python script has changed

import helper
imp.reload(helper)
```
* Edit code in a text editor, reload in the Blender text editor (using the exclamation point icon on top) and click play to re-register operations. This can be followed by re-running the previous step to have a programming workflow. 
