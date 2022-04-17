bl_info = {
    "name": "Animation Transfer",
    "description": "Takes the animation data from a model to another. Rotations have to be in the LOCAL POSE BONE reference.",
    "author": "Andres Otero Garcia",
    "version": (1, 1),
    "blender": (2, 93, 0),
    "location": "View3D > Object > Animation",
    "category": "Animation"}

import json
import itertools
import mathutils
import bpy
import re
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper
from copy import copy
from math import ceil
from collections import defaultdict
import numpy as np

def get_data_bone(armature, idx):
  return list(armature.data.bones)[idx]

def get_pose_bone(armature, idx):
  return list(armature.pose.bones)[idx]

bone_names = ["root", "hip", "spine_01", "spine_02", "spine_03", \
  "head", "head_end", "jaw", "jaw_end", "neck", \
  "eye_r", "eye_end_r", "eyelid_r", "eyelid_end_r", "eyebrow_r", "mouth_r", \
  "eye_l", "eye_end_l", "eyelid_l", "eyelid_end_l", "eyebrow_l", "mouth_l", \
  "shoulder_r", "upperarm_r", "upperarm_twist_r", "lowerarm_r", "lowerarm_twist_r", "hand_r", \
  "shoulder_l", "upperarm_l", "upperarm_twist_l", "lowerarm_l", "lowerarm_twist_l", "hand_l", \
  
  "upperleg_r", "upperleg_twist_r", "lowerleg_r", "lowerleg_twist_r", "foot_r", "ball_r", "foot_end_r" \
  "upperleg_l", "upperleg_twist_l", "lowerleg_l", "lowerleg_twist_l", "foot_l", "ball_l", "foot_end_l"]

finger_names = ["thumb", "index", "middle", "ring", "pinky"]
finger_part_names = ["_01_r", "_01_l", "_02_r", "_02_l", "_03_r", "_03_l", "_end_r", "_end_l"]


def ShowMessage(icon = 'INFO', title = "Message Box", message = ""):
    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

class PanelOne(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_test_3"
    bl_label = "Animation Transfer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"

    def invoke(self, context, event):
      wm = context.window_manager
      return wm.invoke_props_dialog(self)

    def draw(self, context):
      col = self.layout.column(align=True)
      col.label(text="Transfer")
      col.operator("animation.transfer_animation", text="Legacy Animation Transfer")
      col.operator("animation.transfer_animation_custom", text="Animation Transfer (JSON)")
      
      col = self.layout.column(align=True)
      col.label(text="Make stationary")
      col.prop(context.scene, "root_bone_name")
      col.operator("animation.remove_root_movement", text="Make bone stationary")
      

class MyEuler(mathutils.Euler):
  def to_matrix(self):
    m = mathutils.Matrix.Identity(4)
    for i, axis in enumerate(self.order):
      m = m @ mathutils.Matrix.Rotation(self[i], 4, axis)
    return m
  def to_quaternion(self):
    return self.to_matrix().to_quaternion()

def euler_zxz(values):
  """
  Creates a Euler rotation in notation ZXZ from a list of values.
  :param values: List of values
  :return: Euler rotation in notation ZXZ
  """
  rotation = MyEuler((values[0], values[1], 0), 'ZXY')
  rotation.rotate(MyEuler((values[2], 0, 0), 'ZXY'))
  return rotation

def axis_angle_to_quaternion(axis, angle):
  qx = axis[0] * np.sin(angle/2)
  qy = axis[1] * np.sin(angle/2)
  qz = axis[2] * np.sin(angle/2)
  qw = np.cos(angle/2)
  return mathutils.Quaternion((qx, qy, qz, qw))

class Transformation():
  def Identity():
    R = mathutils.Matrix.Identity(3)
    t = mathutils.Vector((0, 0, 0))
    return Transformation(R, t)

  def __init__(self, ori, trans):
    self._ori = ori
    self._trans = trans

  def build_matrix(self):

    if self._ori is None:
      rot = mathutils.Matrix.Identity(3)
    else:
      rot = self._ori

    if self._trans is None:
      loc = mathutils.Vector((0, 0, 0))
    else:
      loc = self._trans
    
    return mathutils.Matrix.Translation(loc) @ rot.to_4x4()


  def apply(self, target_object, target_bone_key):
    if self._ori is not None or self.trans is not None:
      
      armature_modifiers = []

      #Unassign the object of the armature modifier for all the meshes
      for mesh in target_object.children:
        for mod in mesh.modifiers:
          if mod.type == 'ARMATURE' and mod.object == target_object:
            armature_modifiers.append(mod)
            mod.object = None

      bpy.ops.object.mode_set(mode='EDIT')

      edit_bone = target_object.data.edit_bones.get(target_bone_key)
      pose_bone = target_object.pose.bones.get(target_bone_key)

      #Disconnect the bases of the bones from one another (so they don't move with this transformation)
      edit_bone.use_connect = False
      for c in edit_bone.children:
        c.use_connect = False

      bpy.ops.armature.select_all(action='DESELECT')
      edit_bone.select = True

      bone_head_matrix = pose_bone.matrix
      

      if self._ori is not None:
            # Need to transform the orientation to WORLD space
        #Translate to (0,0,0), rotate and then bring back to original position
        R = self._ori.to_4x4()

      if self._trans is not None:
        R = mathutils.Matrix.Translation(self._trans) @ R

      
      
      T = bone_head_matrix @ R
      edit_bone.matrix = T

      bpy.ops.object.mode_set(mode='OBJECT')

      #Once the transformation has been completed, reassign the object in the armature modifier
      for mesh in target_object.children:
        for mod in mesh.modifiers:
          if mod.type == 'ARMATURE' and mod.object == None:
            mod.object = target_object


class Relation():
  def __init__(self, origin, target, offset):
    self.__origin = re.compile('(.*)' + origin + '$')
    self.__target = re.compile('(.*)' + target + '$')
    self.__offset = offset

  def get_origin(self):
    return self.__origin

  def get_target(self):
    return self.__target

  def get_offset(self):
    if self.__offset is None:
      return Transformation.Identity()
    else:
      return self.__offset



def find_armature(obj):
  """
  Finds the armature object from the selected object in Blender.
  :param obj: Object selected through the Blender interface.
  :returns:
    - ret - Outputs True if the function was able to find the armature and False otherwise
    - armature - If the armature was found, returns the armature object. Returns None otherwise.
  """
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
  """
  Finds the origin object for the animation transfer.
  :param active: Active object from Blender (Target object)
  :param selected: List with all the selected objects in Blender
  :return: The first object in the list of selected that is not equal to active. If no such object exists, returns None
  """
  for obj in selected:
    if active != obj:
      return obj
  return None


#-----------------------------------------
"""class AnimationTransferMenu(bpy.types.Menu):
  bl_label = "Animation Transfer"
  bl_idname = "animation_transfer_menu"
  bl_options = {'REGISTER'}

  def draw(self, context):
    layout = self.layout
    layout.operator(AnimationTransfer.bl_idname, text=AnimationTransfer.bl_label)
    layout.operator(AnimationTransferCustom.bl_idname, text=AnimationTransferCustom.bl_label)

def draw_menu(self, context):
  self.layout.menu(AnimationTransferMenu.bl_idname)"""


class Warning():
  def __init__(self, msg):
    self.msg = msg

# -----------------------------------------
class BaseAnimationTransfer():

  regular_expressions = []

  def __init__(self, expr = []):
      self._relations = expr

  def get_matches(self, relations, origin_bones, target_bones):
    """
    Finds the indices in the origin and target armatures of the bones given by the regular expressions that match the bones
    :param relations: List of Relation instances with the regular expression for the origin and target bones
    :param origin_bones: List of the names of the bones in the origin object
    :param target_bones: List of the names of the bones in the target object
    :return: List of indices tuples (t,i,j) where: relations[t].get_origin() matches origin_bones[i] and relations[t].get_target() matches target_bones[j]
    """
    matches = []
    for t, r in enumerate(relations):
      for i, b in enumerate(origin_bones):
        if r.get_origin().match(b):
          for j, b in enumerate(target_bones):
            if r.get_target().match(b):
              matches.append((t, i, j))
    return matches

  def transfer(self, context):
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
    matches = self.get_matches(self._relations, origin_object.data.bones.keys(), target_object.data.bones.keys())
    n = len(matches)
    if n > 0:  
      ShowMessage('INFO', 'Matches', "Found " + str(len(matches)) + " matches between armatures.")
      self.report({'INFO'}, "Found " + str(len(matches)) + " matches between armatures.")
    else:
      self.report({'WARNING'}, "Found no matches between armatures!")

    #Get the animation
    animation = origin_object.animation_data.action
    if animation == None:
      self.report({'ERROR'}, "Origin object " + origin_object.name + " does not have an animation")
      return {'CANCELLED'}

    #Clear original animation
    target_object.animation_data_clear()
    origin_object.data.pose_position='REST'
    target_object.data.pose_position='REST'

    origin_object.select_set(False)

    selected_frame = bpy.context.scene.frame_current
    last_frame = ceil(animation.frame_range[1]) + 1
    frames = np.arange(last_frame)

    #Apply the translations and rotations to all the matching bones in the target armature, for all the keyframes in the animation
    for r_idx, o_idx, t_idx in matches:
          
      target_bone = get_pose_bone(target_object, t_idx)
      origin_bone = get_pose_bone(origin_object, o_idx)
      offset = self._relations[r_idx].get_offset()
      
      offset.apply(target_object, target_bone.name)
      bpy.context.view_layer.update()

    origin_object.data.pose_position='POSE'
    target_object.data.pose_position='POSE'

    for r_idx, o_idx, t_idx in matches:
      target_bone = get_pose_bone(target_object, t_idx)
      origin_bone = get_pose_bone(origin_object, o_idx)
      
      for frame in range(last_frame):
        bpy.context.scene.frame_set(frame)

        target_bone.location = origin_bone.location
        target_bone.rotation_quaternion = origin_bone.rotation_quaternion

        target_bone.keyframe_insert("location", frame=frame)
        target_bone.keyframe_insert("rotation_quaternion", frame=frame)
    
    bpy.context.scene.frame_set(selected_frame)

    return {'FINISHED'}

class AnimationTransfer(BaseAnimationTransfer, bpy.types.Operator):
  bl_idname = "animation.transfer_animation"
  bl_label = "Legacy Animation Transfer"
  
  def __init__(self, expr = []):
    if expr == []:
      if AnimationTransfer.regular_expressions == []:
        for b in bone_names:
          AnimationTransfer.regular_expressions.append(Relation(b, b, None))
        for f in finger_names:
          for p in finger_part_names:
            AnimationTransfer.regular_expressions.append(Relation(f + p, f + p, None))
        AnimationTransfer.regular_expressions = list(AnimationTransfer.regular_expressions)
      self._relations = AnimationTransfer.regular_expressions
    else:
      super()

  def execute(self, context):
    return self.transfer(context)


# -----------------------------------------
class AnimationTransferCustom(BaseAnimationTransfer, ImportHelper, bpy.types.Operator):
  bl_idname = "animation.transfer_animation_custom"
  bl_label = "Animation Transfer (JSON)"

  filter_glob: StringProperty(
    default='*.json',
    options={'HIDDEN'}
  )

  def __init__(self):
    self._relations = []
    self._warnings = []

  def safe_get(self, dic, prop, mandatory=True):
    """
    Finds, within a dictionary (decoded by JSON) a key-value pair with the specified key.
    :param dic: Dictionary in which to search
    :param prop: Key for the pair to search
    :param mandatory: Whether it is mandatory to find such key or not.
    :returns:
      If found, returns the value associated to the specified key.
      If not mandatory and not found within the dictionary, returns None
    :raises:
      JSONDecodeError - If the key was not found, but mandatory was True
    """
    if prop in dic:
      return dic[prop]
    elif mandatory:
      raise json.JSONDecodeError("Malformed JSON: Missing " + prop + " key!", self.filepath, -1)
    else:
      return None

  def expand_bone(self, bone):
    """
    Decodes a JSON field that encodes the name of a group of bones and returns the list of names.
    :param bone: JSON 'bone' field.
    :returns:
      If the bone only possesses a field 'name', returns a list with the value in such key.
      If the bone possesses a field 'suffixes', returns a list containing, for each suffix, the concatenation of the prefix and the suffix.
      If any of such suffixes had a 'subsuffixes' field, all possible combinations of suffixes and subsuffixes are considered suffixes, and the previous case applies.
    :raises:
      JSONDecodeError - If the key 'name' was not found, or if any suffix dictionary does not possess the 'names' tag.
    """
    if type(bone) is not dict:
      return [bone]
    else:
      preffix = self.safe_get(bone, 'name')
      suf_iter = self.safe_get(bone, 'suffixes', False)
      suffixes_names = [""]

      #Treat recursive subsuffixes
      while suf_iter is not None:
        if isinstance(suf_iter, list):
          suffixes_names = [s[0] + s[1] for s in itertools.product(suffixes_names, suf_iter)]
        else:
          current_names = self.safe_get(suf_iter, 'names')
          suffixes_names = [s[0] + s[1] for s in itertools.product(suffixes_names, current_names)]

        #Advance in the recursion of suffixes
        suf_iter = self.safe_get(suf_iter, 'subsuffixes', False)

    return [preffix + s for s in suffixes_names]

  def expand_offset(self, offset):
    """
    Decodes a JSON field that encodes the offset from the origin bone to the target bone, in position and orientation.
    Position is encoded in [x,y,z]
    Orientation can have a dictionary with a codification field of the following:
     - Quaternions
     - Axis-angle
     - RPY
     - Euler ZXZ
     - Rotation matrix
     (and their corresponding values).
     It can also be set to 'identity'.
    :returns:
      - t: A mathutils.Matrix encoding the transformation from the origin bone to the target bone
      - warnings: A list of warnings that may have appeared during the execution (for example, if position or orientation elements).
    :raises:
      - JSONDecodeError: If any of the rotation codifications was malformed, including information on what went wrong.
    """
    result = []
    if not isinstance(offset, list):
      raise json.JSONDecodeError("Malformed JSON: Offset of a bone must always be a list.", self.filepath, -1)
    for t in offset:
      position = self.safe_get(t, 'position', False)
      orientation = self.safe_get(t, 'orientation', False)
      warnings = []

      if position is None:
        warnings.append(Warning("Position was not specified in offset field. Assuming the position offset to be none."))
        pos = mathutils.Vector((0, 0, 0))

      else:
        pos = position


      if orientation is None:
        warnings.append(Warning("Orientation was not specified in offset field. Assuming the orientation offset to be none."))
        rot = mathutils.Matrix.Identity(3)

      elif orientation == 'identity':
        rot = mathutils.Matrix.Identity(3)

      else:
        codif = self.safe_get(orientation, 'codification')
        values = self.safe_get(orientation, 'values')
        

        if codif == 'quaternion':
          #[qx, qy, qz, qw]
          if len(values) != 4:
            raise json.JSONDecodeError("Malformed JSON: Quaternion codification is not correct. (Must include [qx, qy, qz, qw]", self.filepath, -1)

          rot = mathutils.Quaternion(values).to_matrix()

        elif codif == 'rpy':
          #'roll', 'pitch', 'yaw' fields
          roll = self.safe_get(values, 'roll', False)
          pitch = self.safe_get(values, 'pitch', False)
          yaw = self.safe_get(values, 'yaw', False)
          if not isinstance(values, dict) or roll is None or pitch is None or yaw is None:
            raise json.JSONDecodeError("Malformed JSON: RPY codification is not correct. (Must be a dictionary including 'roll', 'pitch' and 'yaw' fields)", self.filepath, -1)

          rot = MyEuler((roll, pitch, yaw), 'XYZ').to_matrix()

        elif codif == 'euler':
          #[Z, X, Z]
          if len(values) != 3:
            raise json.JSONDecodeError("Malformed JSON: Euler codification is not correct. (Must include [phi (Z), theta (X), psi (Z)]", self.filepath, -1)
          rot = euler_zxz(values).to_matrix()

        elif codif == 'axis_angle':
          # for i = 1..3:
          #   [axis_i (vector), th_i] OR [x_i, y_i, z_i, th_i]
          rot = mathutils.Matrix.Identity(3)
          if len(values) != 3:
            raise json.JSONDecodeError("Malformed JSON: Axis-angle codification is not correct. (Must include 3 elements of the form [[axis_i], angle_i] or [axis_i_x, axis_i_y, axis_i_z, angle_i]", self.filepath, -1)
          for i,aa in enumerate(values):
            if len(aa) == 4:
              rot = rot @ mathutils.Rotation(values[i][3], 3, values[i][0:3])
            elif (len(aa) == 2 and len(aa[0]) == 3 and isinstance(aa[1], float)):
              rot = rot @ mathutils.Rotation(values[i][1], 3, values[i][0])
            else:
              raise json.JSONDecodeError("Malformed JSON: Axis-angle codification is not correct: (Must include 3 elements of the form [[axis_i], angle_i] or [axis_i_x, axis_i_y, axis_i_z, angle_i]", self.filepath, -1)

        elif codif == 'rotation_matrix':
          # [first row, second row, third row] (all vectors of size 3)
          if len(values) != 3:
            raise json.JSONDecodeError("Malformed JSON: Rotation matrix codification is not correct: (Must include [[nx, ox, ax], [ny, oy, ay], [nz, oz, az]]", self.filepath, -1)
          for i in values:
            if len(i) != 3:
              raise json.JSONDecodeError("Malformed JSON: Rotation matrix codification is not correct: (Must include [[nx, ox, ax], [ny, oy, ay], [nz, oz, az]]", self.filepath, -1)
          rot = mathutils.Matrix(values)

        else:
          raise json.JSONDecodeError("Malformed JSON: Unknown codification: " + codif + ".\nPossible values: 'quaternion', 'rpy', 'euler', 'axis_angle' and 'rotation_matrix'.", self.filepath, -1)
      
      #if switch_axes is not None:
      #  if not isinstance(switch_axes, dict):
      #    raise json.JSONDecodeError("Malformed JSON: Switcing must be a dictionary. (Must include fields X, Y and Z)", self.filepath, -1)
      #  X = self.safe_get(switch_axes, 'X', False)
      #  Y = self.safe_get(switch_axes, 'Y', False)
      #  Z = self.safe_get(switch_axes, 'Z', False)
      #  if X is None or Y is None or Z is None:
      #    raise json.JSONDecodeError("Malformed JSON: Switcing must be a dictionary. (Must include fields X, Y and Z)", self.filepath, -1)
      #  basis = create_switch_axes((X, Y, Z))
      #  rot = basis @ rot

      t = Transformation(rot, pos)
      
      result.append(t)
    return result, warnings

  def expand_rel(self, rel):
    """
    Decodes a JSON field that encodes the relations between a bone (with subvariants, i.e. bone_r and bone_l) in the origin armature and those from the target armature.
    :returns:
      - t: A Relation list encoding the transformations from the origin bones to the target bones
      - warnings: A list of warnings that may have appeared during the execution (for example, if position or orientation elements).
    :raises:
      - JSONDecodeError: If any of the rotation codifications was malformed, including information on what went wrong.
    """
    origin = self.safe_get(rel, 'origin')
    target = self.safe_get(rel, 'target', False)
    offset = self.safe_get(rel, 'offset', False)

    origin_exp = self.expand_bone(origin)

    if target is None:
      target = origin

    target_exp = self.expand_bone(target)
    w = []

    if len(origin_exp) != len(target_exp):
      raise json.JSONDecodeError("Malformed JSON: The number of suffixes in origin bones must match the suffixes on target bones, or target's should be left empty." + str(len(origin_exp)) + " != " + str(len(target_exp)), self.filepath, -1)

    if offset is not None:
      offset_t, _ = self.expand_offset(offset)
    else:
      offset_t = list(itertools.repeat(None, len(origin_exp)))
    
    if len(offset_t) != len(origin_exp):
      raise json.JSONDecodeError("Malformed JSON: If present, the number of transformation matrices in bones must match the number of suffixes, so there are as many matrices as bones. If no transformation is required for certain bone, codification 'identity' may be used." + str(len(offset_t)) + " != " + str(len(origin_exp)), self.filepath, -1)

    return [Relation(ori, tar, off) for ori, tar, off in zip(origin_exp, target_exp, offset_t)], w

  def expand_relations(self, dic):
    relations = self.safe_get(dic, 'relations')
    if relations is None: 
      return None
    if type(relations) is not list:
      self.report({'ERROR'}, "Malformed JSON: Relations object must be an array")
      return -2

    try:
      for rel in dic['relations']:
        relations, warnings = self.expand_rel(rel)
        self._relations += relations
        self._warnings += warnings
    except json.JSONDecodeError as e:
      self.report({'ERROR'}, repr(e))
      return -2

    return 0

  def execute(self, context):
    f = open(self.filepath, 'r')
    print('Chosen file', self.filepath)
    try:
      data = json.load(f)
    except json.JSONDecodeError as e:
      self.report({'ERROR'}, "Malformed JSON: " + str(e))
      return {'CANCELLED'}
    if self.expand_relations(data) != 0:
      return {'CANCELLED'}

    for w in self._warnings:
      self.report({'WARNING'}, w.msg)
    
    return self.transfer(context)
# -------------------------------------------------------------------------------------------

# -----------------------------------------
class RemoveRootMovement(bpy.types.Operator):
    bl_idname = "animation.remove_root_movement"
    bl_label = "Make Stationary"
    bl_options = {'REGISTER'}

    def __init__(self):
      root_name = bpy.context.scene.root_bone_name
      self.root_re = re.compile('(.*)' + root_name + '$')

    def get_root_idx(self, bones):
      for i,b in enumerate(bones):
        if self.root_re.match(b.name):
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
      idx = self.get_root_idx(target_object.data.bones)

      if idx == -1:
        self.report({'ERROR'}, "Could not find 'root' bone.")
        return {'CANCELLED'}

      ini_location = mathutils.Vector((0.0, 0.0, 0.0))

      #Delete all location keyframes from root
      for frame in range(ceil(animation.frame_range[1]) + 1):
        bpy.context.scene.frame_set(frame)
        get_pose_bone(target_object, idx).location = ini_location
        get_pose_bone(target_object, idx).keyframe_insert("location", frame=frame)

      bpy.context.scene.frame_set(selected_frame)
      
      return {'FINISHED'}


def register():
  bpy.types.Scene.root_bone_name = bpy.props.StringProperty \
      (
        name = "Root bone",
        description = "The name of the bone which we want to be stationary",
        default = 'root'
      )

  bpy.utils.register_class(AnimationTransfer)
  bpy.utils.register_class(AnimationTransferCustom)
  bpy.utils.register_class(RemoveRootMovement)
  bpy.utils.register_class(PanelOne)
  

def unregister():
  del bpy.types.Scene.root_bone_name
  bpy.utils.unregister_class(PanelOne)
  bpy.utils.unregister_class(AnimationTransferCustom)
  bpy.utils.unregister_class(RemoveRootMovement)
  bpy.utils.unregister_class(AnimationTransfer)
  


if __name__ == "__main__":
  register()
