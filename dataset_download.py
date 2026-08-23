from roboflow import Roboflow
rf = Roboflow(api_key="D7na50m8yffNinIfHDnf")
project = rf.workspace("darf1").project("vehicle-detection-kaogt")
dataset = project.version(1).download("yolo26")