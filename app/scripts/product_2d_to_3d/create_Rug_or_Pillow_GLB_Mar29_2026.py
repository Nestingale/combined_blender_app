import bpy
import os
import sys
# sys.path.append("/home/ubuntu/blender_addons/python_libs")

import tempfile
from PIL import Image
import numpy as np
import urllib.request
import urllib.parse
import math
import mathutils

# --- Utility Functions ---

def download_image_from_url(url):
    """Download an image from URL to temporary file."""
    try:
        temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response, open(temp_path, 'wb') as out_file:
            out_file.write(response.read())
        return temp_path
    except Exception as e:
        print(f"Error downloading image from {url}: {e}")
        return None

def validate_image_file(image_path):
    """Validate if file is a supported image and exists."""
    if not image_path or not os.path.exists(image_path):
        return False
    try:
        with Image.open(image_path) as img:
            img.verify()
        return True
    except Exception as e:
        print(f"Invalid image {image_path}: {e}")
        return False

def get_image_file(image_path_or_url):
    """Get local file path, downloading if URL. Returns (path, is_temp)."""
    if not image_path_or_url:
        return None, False
    if image_path_or_url.startswith(('http://', 'https://')):
        path = download_image_from_url(image_path_or_url)
        return path, (path is not None)
    return image_path_or_url, False

def clear_scene():
    """Clear Blender scene completely."""
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for block in [bpy.data.meshes, bpy.data.materials, bpy.data.textures, bpy.data.images]:
        for item in block:
            block.remove(item)

def parse_arguments():
    """Parse command line arguments."""
    try:
        separator_index = sys.argv.index('--')
        script_args = sys.argv[separator_index + 1:]
    except ValueError:
        script_args = []
    
    if not script_args:
        print("Usage: blender -b -P script.py -- --rug|--pillow <image1> [image2]")
        sys.exit(1)

    if script_args[0] == '--rug':
        return 'rug', script_args[1:]
    elif script_args[0] == '--pillow':
        return 'pillow', script_args[1:]
    else:
        print(f"Invalid mode: {script_args[0]}. Use --rug or --pillow")
        sys.exit(1)

# --- Rug Functions ---

def remove_white_edges_precise_rug(image_path, threshold=240):
    """Process rug image to remove white borders and resize."""
    try:
        image = Image.open(image_path).convert('RGB')
        img_array = np.array(image)
        non_white_mask = np.any(img_array < threshold, axis=2)
        
        if not np.any(non_white_mask):
            print("Warning: No non-white content found in rug image")
            cropped = image
        else:
            rows = np.any(non_white_mask, axis=1)
            cols = np.any(non_white_mask, axis=0)
            top, bottom = np.where(rows)[0][[0, -1]]
            left, right = np.where(cols)[0][[0, -1]]
            cropped = image.crop((left, top, right + 1, bottom + 1))

        resizeFactor = 2
        resized = cropped.resize((646 * resizeFactor, 1024 * resizeFactor), Image.Resampling.LANCZOS)
        final = Image.new('RGB', (1024 * resizeFactor, 1024 * resizeFactor), (0, 0, 0))
        final.paste(resized, (0, 0))
        
        temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        final.save(temp_file, format='JPEG')
        return final, temp_file.name
        
    except Exception as e:
        print(f"Error processing rug image: {e}")
        raise

def setup_material_nodes(material, texture_path):
    """Robustly setup material nodes to use a specific texture."""
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    
    # Find or create Principled BSDF
    principled = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not principled:
        principled = nodes.new('ShaderNodeBsdfPrincipled')
        # Link to output
        output = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if not output:
            output = nodes.new('ShaderNodeOutputMaterial')
        links.new(principled.outputs['BSDF'], output.inputs['Surface'])

    # Clear existing texture nodes
    for node in list(nodes):
        if node.type == 'TEX_IMAGE':
            nodes.remove(node)
            
    # Create new texture node
    tex_node = nodes.new('ShaderNodeTexImage')
    try:
        img = bpy.data.images.load(texture_path)
        tex_node.image = img
        tex_node.image.colorspace_settings.name = 'sRGB'
    except Exception as e:
        print(f"Error loading texture {texture_path}: {e}")
        
    links.new(tex_node.outputs['Color'], principled.inputs['Base Color'])
    return tex_node

def replace_textures_in_glb_rug(glb_path, diffuse_path, output_path, base_name):
    """Replace textures in rug GLB and renames parent."""
    try:
        clear_scene()
        bpy.ops.import_scene.gltf(filepath=glb_path)
        
        if not bpy.context.scene.objects:
            raise ValueError("No objects found in rug base GLB")

        # Rename root
        root = next((obj for obj in bpy.context.scene.objects if not obj.parent), bpy.context.scene.objects[0])
        root.name = base_name
        
        # Apply texture to first material found
        if not bpy.data.materials:
            bpy.data.materials.new(name="RugMaterial")
        
        material = bpy.data.materials[0]
        setup_material_nodes(material, diffuse_path)
        
        bpy.ops.export_scene.gltf(filepath=output_path, export_format='GLB')
        print(f"Successfully exported rug GLB to: {output_path}")
        
    except Exception as e:
        print(f"Error processing rug GLB: {e}")
        raise

# --- Pillow Functions ---

def remove_white_background_pillow(image_path, threshold=240):
    """Removes white background and creates 1024x1024 diffuse map."""
    try:
        image = Image.open(image_path)
        if image.mode == 'RGBA':
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        img_array = np.array(image)
        non_white_mask = np.any(img_array < threshold, axis=2)

        if not np.any(non_white_mask):
            cropped = image
        else:
            rows = np.any(non_white_mask, axis=1)
            cols = np.any(non_white_mask, axis=0)
            top, bottom = np.where(rows)[0][[0, -1]]
            left, right = np.where(cols)[0][[0, -1]]
            cropped = image.crop((left, top, right + 1, bottom + 1))

        diffuse_map = cropped.resize((1024, 1024), Image.Resampling.LANCZOS)
        diffuse_map = diffuse_map.transpose(Image.FLIP_LEFT_RIGHT)
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            diffuse_map.save(temp_file, format='JPEG')
            temp_path = temp_file.name
        return temp_path
    except Exception as e:
        print(f"Error processing pillow image: {e}")
        raise

def replace_textures_in_glb_pillow(glb_path, front_path, back_path, output_path, base_name):
    """Replace textures for front and back meshes in pillow GLB."""
    try:
        clear_scene()
        bpy.ops.import_scene.gltf(filepath=glb_path)

        front_mesh = None
        back_mesh = None
        
        # Enhanced detection: Check object name AND parent name
        for obj in bpy.context.scene.objects:
            if obj.type == 'MESH':
                search_str = (obj.name + (obj.parent.name if obj.parent else "")).lower()
                if 'front' in search_str:
                    front_mesh = obj
                elif 'back' in search_str:
                    back_mesh = obj
                
                obj.location = (0,0,0) # Center everything

        # Fallback if naming is completely non-standard
        if not front_mesh or not back_mesh:
            print("Warning: Naming non-standard. Falling back to mesh order.")
            meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
            if len(meshes) >= 2:
                front_mesh = meshes[0]
                back_mesh = meshes[1]
            elif len(meshes) == 1:
                front_mesh = back_mesh = meshes[0]
            else:
                raise ValueError("No meshes found in pillow base GLB")

        # Setup Materials
        for mesh, tex in [(front_mesh, front_path), (back_mesh, back_path)]:
            if not mesh.data.materials:
                mat = bpy.data.materials.new(name=f"Mat_{mesh.name}")
                mesh.data.materials.append(mat)
            setup_material_nodes(mesh.data.materials[0], tex)

        bpy.ops.export_scene.gltf(filepath=output_path, export_format='GLB')
        print(f"Successfully exported pillow GLB to: {output_path}")

    except Exception as e:
        print(f"Error during pillow GLB processing: {e}")
        raise

# --- Main Function ---

def main():
    mode, image_args = parse_arguments()
    script_dir = os.path.dirname(os.path.realpath(__file__))
    downloaded_files = []
    temp_diffuses = []
    
    try:
        if mode == 'rug':
            img_input = image_args[0] if image_args else None
            if not img_input:
                print("Error: Rug requires an image")
                sys.exit(1)
            
            base_name = os.path.splitext(os.path.basename(img_input.split('?')[0]))[0]
            img_path, is_temp = get_image_file(img_input)
            if is_temp: downloaded_files.append(img_path)
            
            if not validate_image_file(img_path):
                print(f"Error: Invalid rug image {img_input}")
                sys.exit(1)
                
            glb_base = os.path.join(script_dir, "Rug_New_Basefile.glb")
            _, diffuse_temp = remove_white_edges_precise_rug(img_path)
            temp_diffuses.append(diffuse_temp)
            
            replace_textures_in_glb_rug(glb_base, diffuse_temp, os.path.join(script_dir, "output.glb"), base_name)
            
        elif mode == 'pillow':
            front_input = image_args[0] if len(image_args) > 0 else None
            back_input = image_args[1] if len(image_args) > 1 else front_input # Fallback to front if back missing
            
            if not front_input:
                print("Error: Pillow requires at least one image")
                sys.exit(1)
            
            base_name = os.path.splitext(os.path.basename(front_input.split('?')[0]))[0]
            
            # Get Files
            f_path, f_is_temp = get_image_file(front_input)
            if f_is_temp: downloaded_files.append(f_path)
            
            b_path, b_is_temp = get_image_file(back_input)
            if b_is_temp: downloaded_files.append(b_path)
            
            # Robust validation: if back is invalid, use front
            if not validate_image_file(f_path):
                print(f"Error: Front image invalid")
                sys.exit(1)
            if not validate_image_file(b_path):
                print("Warning: Back image invalid. Using front image for both sides.")
                b_path = f_path

            glb_base = os.path.join(script_dir, "Pillow_75.glb")
            
            f_diffuse = remove_white_background_pillow(f_path)
            temp_diffuses.append(f_diffuse)
            
            b_diffuse = remove_white_background_pillow(b_path)
            temp_diffuses.append(b_diffuse)
            
            replace_textures_in_glb_pillow(glb_base, f_diffuse, b_diffuse, os.path.join(script_dir, "output.glb"), base_name)
            
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        sys.exit(1)
    finally:
        for f in downloaded_files + temp_diffuses:
            if f and os.path.exists(f):
                try: os.remove(f)
                except: pass

if __name__ == "__main__":
    main()
