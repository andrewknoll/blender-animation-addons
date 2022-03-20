# blender-animation-addons

This repository includes two add-ons for Blender (>=2.93) to handle the animation of rigged models.

## Animation Transfer

This add-on takes the animation of a rigged model and applies it to another model with the same bone structure.
The format that is used is compatible with u3d (Universal 3D format) (see [](###skeleton-format))

### Installation
- In Blender, click on `Edit > Preferences`.
- Once there, on the `Add-ons` tab, click on `Install`.
- Navigate and select [`animation_transfer.py`](animation_transfer.py).
- Enable the Add-on.

### Usage
- Import the two models with their rigging: The one with the original animation (we'll call it "origin") and the one to which the animation will be applied (we'll call it "target").
- Select, **in this order**, the original object and the target object (you can either select the Mesh or the Armature from them).
- In Object mode, click `Object > Animation > Transfer Animation`.
- Now, both the target and origin objects will have the same animation (if the target object had an animation prior to this, it will be deleted).

## Skeleton Format
The skeleton format that has been chosen to build these scripts is compatible with u3d (universal 3D) and uses the following naming convention:
- `root`, `hip`, `spine_01`, `spine_ 02`, `spine_03`, `head`, `head_end`, `jaw`, `jaw_end`, `neck`
- The following bones end with `_l` or `_r` depending on the side where they are placed (left or right, respectively):
  - `eye`, `eye_end`, `eyelid`, `eyelid_end`, `eyebrow`, `mouth`
  - `shoulder`, `upperarm`, `upperarm_twist`, `lowerarm`, `lowerarm_twist`
  - `upperleg`, `upperleg_twist`, `lowerleg`, `lowerleg_twist`, `foot`, `ball`, `foot_end`
  - `thumb_01`, `thumb_02`, `thumb_03`
  - `index_01`, `index_02`, `index_03`
  - `middle_01`, `middle_02`, `middle_03`
  - `ring_01`, `ring_02`, `ring_03`,
  - `pinky_01`, `pinky_02`, `pinky_03`

In the case any of these does not match on the two skeletons at the same time, they will be ignored.

## Make Stationary
Some animations that involve a movement, like walking, swimming... move the object forward, so their initial position does not match their final position.
This has some disadvantages if you want to control the movement in an external program, independently from the animation (for example, manually setting the speed of movement).
Therefore, it is common to have the position of the model be fixed rather than the animation moving it forward.
This add-on deletes all the translation that may have been applied to the "root" bone and sets it to the origin of the axes in Blender (position `(0,0,0)`).

### Installation
- In Blender, click on `Edit > Preferences`.
- Once there, on the `Add-ons` tab, click on `Install`.
- Navigate and select [`make_stationary.py`](make_stationary.py).
- Enable the Add-on.

### Usage
- Import the model with its rigging and animation.
- Select the object (you can either select the Mesh or the Armature from it).
- In Object mode, click `Object > Animation > Make Stationary`.
- Now, all the bones will move in the same manner as before, but the root bone will remain in place.
