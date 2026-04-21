import numpy as np
from PIL import Image

def test_masks(img_path):
    img = Image.open(img_path).convert("RGB")
    arr = np.array(img)
    
    r = arr[:,:,0].astype(np.float32)
    g = arr[:,:,1].astype(np.float32)
    b = arr[:,:,2].astype(np.float32)
    
    w_score = (b - r) / (r + g + b + 1e-6)
    v_score = (g - r) / (g + r + b + 1e-6)
    
    # Create mask visualizations
    w_mask = (w_score >= 0.04).astype(np.uint8) * 255
    v_mask = (v_score >= 0.02).astype(np.uint8) * 255
    
    Image.fromarray(w_mask).save("water_mask_test.png")
    Image.fromarray(v_mask).save("veg_mask_test.png")
    
    print(f"Water mean score: {w_score.mean():.3f}, max: {w_score.max():.3f}")
    print(f"Veg mean score: {v_score.mean():.3f}, max: {v_score.max():.3f}")

if __name__ == "__main__":
    test_masks("/home/tanish03/Desktop/UG4-2/SDS/proj/test1.jpg")
