import ezdxf

# 1. إنشاء ملف كاد جديد
doc = ezdxf.new('R2010')
msp = doc.modelspace()

# 2. إنشاء طبقة (Layer) خاصة بالمقابس الكهربائية
doc.layers.new(name='SOCKETS', dxfattribs={'color': 2})

# 3. رسم "مقابس" وهمية (دوائر) في أماكن محددة
# الإحداثيات هنا تمثل الأماكن التي يجب أن يذهب إليها الروبوت
points = [(10, 10), (50, 10), (100, 30)]

for p in points:
    msp.add_circle(p, radius=2, dxfattribs={'layer': 'SOCKETS'})

# 4. حفظ الملف
doc.saveas("site_map.dxf")
print("تم إنشاء ملف site_map.dxf بنجاح!")