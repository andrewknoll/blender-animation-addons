bl_info = {
    "name": "Make Stationary",
    "description": "Removes the movement of the object (movement of bone 'root').",
    "author": "Andres Otero Garcia",
    "version": (1, 0),
    "blender": (2, 93, 0),
    "location": "View3D > Object > Animation",
    "warning": "", # used for warning icon and text in addons panel
    "wiki_url": "",
    "category": "Animation"}


import bpy
import re
from math import ceil
from mathutils import Vector

def find_armature(obj):
  if obj.type == 'ARMATURE':
    return True, obj
  #If it is a mesh but has an armature
  elif obj.type == 'MESH' and obj.parent and obj.parent.type == 'ARMATURE':
    return True, obj.parent
  else:
    for obj in obj.select_more():
      ret, child = find_armature(obj)
      if ret:
        return ret, child
    return False, None

def get_data_bone(armature, idx):
  return list(armature.data.bones)[idx]

def get_pose_bone(armature, idx):
  return list(armature.pose.bones)[idx]
    
# -----------------------------------------
class RemoveRootMovement(bpy.types.Operator):
    bl_idname = "animation.remove_root_movement"
    bl_label = "Make Stationary"
    bl_options = {'REGISTER'}
    root_re = re.compile('(.*)root$')

    def get_root_idx(bones):
      for i,b in enumerate(bones):
        if RemoveRootMovement.root_re.match(b.name):
          return i
      return -1

    def execute(self, context):

      selected_objects = bpy.context.selected_objects

      if bpy.context.active_object is None:
        self.report({'ERROR'}, "Could not retrieve target object.")
        return {'CANCELLED'}

      #Find the armatures from the selected objects
      ret_t, target_object = find_armature(bpy.context.active_object)

      if not ret_t:
        self.report({'ERROR'}, "Target object " + bpy.context.active_object.name + " does not have an armature")
        return {'CANCELLED'}
      
      #Get the animation
      animation = target_object.animation_data.action
      if animation == None:
        self.report({'WARN'}, "Target object " + target_object.name + " does not have an animation. No operation applied.")
        return {'CANCELLED'}
            
      selected_frame = bpy.context.scene.frame_current
      idx = RemoveRootMovement.get_root_idx(target_object.data.bones)

      if idx == -1:
        self.report({'ERROR'}, "Could not find 'root' bone.")
        return {'CANCELLED'}

      ini_location = Vector((0.0, 0.0, 0.0))

      #Delete all location keyframes from root
      for frame in range(ceil(animation.frame_range[1]) + 1):
        bpy.context.scene.frame_set(frame)
        get_pose_bone(target_object, idx).location = ini_location
        get_pose_bone(target_object, idx).keyframe_insert("location", frame=frame)

      bpy.context.scene.frame_set(selected_frame)
      
      return {'FINISHED'}
# -------------------------------------------------------------------------------------------

def menu_func(self, context):
  self.layout.operator(RemoveRootMovement.bl_idname, text=RemoveRootMovement.bl_label)
   

def register():
  bpy.utils.register_class(RemoveRootMovement)
  bpy.types.VIEW3D_MT_object_animation.append(menu_func)

def unregister():
  bpy.utils.unregister_class(RemoveRootMovement)
  bpy.types.VIEW3D_MT_object_animation.remove(menu_func)


if __name__ == "__main__":
  register()