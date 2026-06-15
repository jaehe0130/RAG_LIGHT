from PIL import Image, ImageDraw, ImageFont
import os

img = Image.new('RGB', (800, 600), color=(255, 255, 255))
draw = ImageDraw.Draw(img)

font_path = "C:/Windows/Fonts/malgun.ttf"
try:
    font = ImageFont.truetype(font_path, 24)
except IOError:
    font = ImageFont.load_default()

text = """
[피트니스 센터 회원권 이용 약관]

제 1조 (계약 해지 및 위약금)
본 피트니스 센터의 회원권은 특가 할인 상품이므로, 중도 계약 해지 시 
총 결제 금액의 50%가 위약금으로 부과됩니다.

제 2조 (회원권 양도)
회원권 타인 양도 시 양도 수수료는 50,000원 입니다.

제 3조 (환불 규정)
등록 후 3일이 경과하거나 시설을 1회 이상 이용한 경우 절대 환불 불가합니다.

제 4조 (책임)
센터 내에서 발생한 개인 물품 분실에 대해 센터는 일절 책임지지 않습니다.
"""

draw.text((50, 50), text.strip(), fill=(0,0,0), font=font)
img.save('c:/projects/RAG_light/sample_contract.png')
print("Sample contract image generated at c:/projects/RAG_light/sample_contract.png")
