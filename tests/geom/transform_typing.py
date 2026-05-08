from cad import circle, prism, rectangle

rectangle((0, 0), (1, 1)).translate(2, 0)
rectangle((0, 0), (1, 1)).translate(2, 0, 0)
prism((0, 0, 0), (1, 1, 1)).translate(1, 0, 0)
prism((0, 0, 0), (1, 1, 1)).translate(1, 0)
circle((0, 0), 1).with_hole(circle((0, 0), 0.5))
prism((0, 0, 0), (1, 1, 1)).with_hole(circle((0, 0), 0.5))
