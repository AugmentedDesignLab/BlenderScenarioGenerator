# BlenderScenarioGenerator
Generate roads and scenarios for testing autonomous vehicles in simulation using Blender python scripting. Output will be an OpenDRIVE file, an OpenSCENARIO file and an FBX file. All three of these formats can be imported into autonomous vehicle simulators such as CARLA. 

## Getting started
* First, [download and install Blender](https://www.blender.org/download/). This is a 3D modeling tool. It has a [Python API](https://docs.blender.org/api/current/info_overview.html). This repository contains python scripts that make use of this API for generating roads.
* Add the [Blender installation directory](https://docs.blender.org/manual/en/latest/advanced/command_line/launch/index.html) to the environment variable such that the command *blender* can be accessed from the command line. 
* Clone this repository and change directory to it. 
* Run the python script *road_base.py* using the **Blender python only**. This will *register* the *pr* (procedural roads) set of operations.
* Run from the Blender python console, *bpy.ops.pr.road()*. This should generate a road in the 3D viewport.  
