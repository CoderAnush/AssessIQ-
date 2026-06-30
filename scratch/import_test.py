import os, sys, traceback, importlib
root = os.path.abspath('c:/Users/anush/Desktop/SHL/AssessIQ-')
sys.path.append(root)
try:
    importlib.import_module('app.services.retriever')
    print('IMPORT SUCCESS')
except Exception as e:
    print('IMPORT FAILURE')
    traceback.print_exc()
