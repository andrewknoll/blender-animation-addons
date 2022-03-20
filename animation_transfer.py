bl_info = {
    "name": "Animation Transfer",
    "description": "Takes the animation data from a model to another.",
    "author": "Andres Otero Garcia",
    "version": (1, 0),
    "blender": (2, 93, 0),
    "location": "View3D > Object > Animation",
    "warning": "Both models must have U3D naming convention.", # used for warning icon and text in addons panel
    "wiki_url": "",
    "category": "Animation"}


import bpy
import re
from copy import copy
from math import ceil

bone_names = ["root", "hip", "spine_01", "spine_02", "spine_03", \
  "head", "head_end", "jaw", "jaw_end", "neck", \
  "eye_r", "eye_end_r", "eyelid_r", "eyelid_end_r", "eyebrow_r", "mouth_r", \
  "eye_l", "eye_end_l", "eyelid_l", "eyelid_end_l", "eyebrow_l", "mouth_l", \
  "shoulder_r", "upperarm_r", "upperarm_twist_r", "lowerarm_r", "lowerarm_twist_r", "hand_r", \
  "shoulder_l", "upperarm_l", "upperarm_twist_l", "lowerarm_l", "lowerarm_twist_l", "hand_l", \
  
  "upperleg_r", "upperlef_twist_r", "lowerleg_r", "lowerleg_twist_r", "foot_r", "ball_r", "foot_end_r" \
  "upperleg_l", "upperlef_twist_l", "lowerleg_l", "lowerleg_twist_l", "foot_l", "ball_l", "foot_end_l"]

finger_names = ["thumb", "index", "middle", "ring", "pinky"]
finger_part_names = ["_01_r", "_01_l", "_02_r", "_02_l", "_03_r", "_03_l", "_end_r", "_end_l"]

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

def get_origin_object(active, selected):
  for obj in selected:
    if active != obj:
      return obj
  return None
    
# -----------------------------------------
class AnimationTransfer(bpy.types.Operator):
    bl_idname = "animation.transfer_animation"
    bl_label = "Transfer Animation"
    bl_options = {'REGISTER'}

    regular_expressions = []

    def __init__(self):
      super()
      if AnimationTransfer.regular_expressions == []:
        for b in bone_names:
          AnimationTransfer.regular_expressions.append(re.compile('(.*)' + b + '$'))
        for f in finger_names:
          for p in finger_part_names:
            AnimationTransfer.regular_expressions.append(re.compile('(.*)' + f + p + '$'))
        AnimationTransfer.regular_expressions = list(enumerate(AnimationTransfer.regular_expressions))

    def find_match(bone, expressions):
      for i,(id,rexp) in enumerate(expressions):
        if rexp.match(bone.name):
          return i,id
      return -1,None

    def get_matches(bones):
      matches = []
      expressions = copy(AnimationTransfer.regular_expressions)
      for b in bones:
        i,id = AnimationTransfer.find_match(b, expressions)
        if i != -1:
          matches.append(id)
          expressions.pop(i)
      return matches

    def execute(self, context):

        if len(bpy.context.selected_objects) != 2:
          self.report({'ERROR'}, "Select two different objects (first origin and then target objects).")
          return {'CANCELLED'}

        if bpy.context.active_object is None:
          self.report({'ERROR'}, "Could not retrieve target object.")
          return {'CANCELLED'}

        origin_container = get_origin_object(bpy.context.active_object, bpy.context.selected_objects)

        if origin_container is None:
          self.report({'ERROR'}, "Could not retrieve origin object.")
          return {'CANCELLED'}

        #Find the armatures from the selected objects
        ret_o, origin_object = find_armature(origin_container)
        ret_t, target_object = find_armature(bpy.context.active_object)

        if not ret_o:
          self.report({'ERROR'}, "Origin object " + bpy.context.selected_objects[1].name + " does not have an armature")
          return {'CANCELLED'}
        if not ret_t:
          self.report({'ERROR'}, "Target object " + bpy.context.active_object.name + " does not have an armature")
          return {'CANCELLED'}
        if origin_object == target_object:
          self.report({'ERROR'}, "Select two different objects (first origin and then target objects).")
          return {'CANCELLED'}

        #Match the names of the armatures with the regular expressions
        matches_origin = AnimationTransfer.get_matches(origin_object.data.bones)
        matches_target = AnimationTransfer.get_matches(target_object.data.bones)

        #Get the animation
        animation = origin_object.animation_data.action
        if animation == None:
          self.report({'ERROR'}, "Origin object " + origin_object.name + " does not have an animation")
          return {'CANCELLED'}

        #Clear original animation
        target_object.animation_data_clear()
              
        selected_frame = bpy.context.scene.frame_current

        #Apply the translations and rotations to all the matching bones in the target armature, for all the keyframes in the animation
        for frame in range(ceil(animation.frame_range[1]) + 1):
          bpy.context.scene.frame_set(frame)
          for idx in set(matches_origin).intersection(matches_target):
            target_bone = list(target_object.pose.bones)[idx]
            origin_bone = list(origin_object.pose.bones)[idx]
            target_bone.location = origin_bone.location
            target_bone.keyframe_insert("location", frame=frame)
            target_bone.rotation_quaternion = origin_bone.rotation_quaternion
            target_bone.keyframe_insert("rotation_quaternion", frame=frame)

        bpy.context.scene.frame_set(selected_frame)
        
        return {'FINISHED'}
# -------------------------------------------------------------------------------------------

def menu_func(self, context):
  self.layout.operator(AnimationTransfer.bl_idname, text=AnimationTransfer.bl_label)
   

def register():
  bpy.utils.register_class(AnimationTransfer)
  bpy.types.VIEW3D_MT_object_animation.append(menu_func)

def unregister():
  bpy.utils.unregister_class(AnimationTransfer)
  bpy.types.VIEW3D_MT_object_animation.remove(menu_func)


if __name__ == "__main__":
  register()