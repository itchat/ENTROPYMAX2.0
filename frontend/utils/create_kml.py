from pykml.factory import KML_ElementMaker as KML
from lxml import etree
import pandas as pd

def _hex_to_kml_color(hex_color, alpha='ff'):
    """Convert '#RRGGBB' hex color to KML 'aabbggrr' format."""
    hex_color = hex_color.lstrip('#')
    r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    return f'{alpha}{b}{g}{r}'.lower()

def create_kml(file_name, k_value, group_number, output_file_name, relabel_mapping=None, group_colors=None):
    '''
    creates kml with data assuming chosen k value
        file_name = input file_name
        k_value = k value to show in kml file
        group_number = group number to show, 0 to show all in k
        relabel_mapping = optional dict {old_group: new_group} for relabeled groups
        group_colors = optional dict {group_label: hex_color} for colored placemarks
    '''
    df = pd.read_parquet(file_name, filters=[('K', '=', k_value)])
    # checks if group number needs to be filtered
    if group_number != 0:
        # If relabeling, find the original group that maps to this new label
        if relabel_mapping:
            reverse_map = {v: k for k, v in relabel_mapping.items()}
            original_group = reverse_map.get(group_number, group_number)
            df = df[df['Group'] == original_group]
        else:
            df = df[df['Group'] == group_number]

    # Build style elements for each group color
    style_map = {}
    if group_colors:
        for label, hex_color in group_colors.items():
            style_id = f'group-style-{label}'
            style_map[label] = style_id

    # initialise document
    doc = KML.kml(KML.Document())

    # Add style definitions
    for label, style_id in style_map.items():
        kml_color = _hex_to_kml_color(group_colors[label])
        style = KML.Style(
            KML.IconStyle(
                KML.color(kml_color),
                KML.scale('1.0'),
                KML.Icon(
                    KML.href('http://maps.google.com/mapfiles/kml/paddle/wht-blank.png')
                ),
            ),
            id=style_id
        )
        doc.Document.append(style)

    # iterate through dataframe, adding each to the document
    for index, row in df.iterrows():
        display_group = row["Group"]
        if relabel_mapping:
            display_group = relabel_mapping.get(int(row["Group"]), row["Group"])

        placemark = KML.Placemark(
            KML.name(row["Sample"]),
            KML.description("group number : %i" %(display_group)),
            KML.Point(
                KML.coordinates("%f,%f,0" %(row["longitude"], row["latitude"]))
            )
        )

        # Apply style if available
        if display_group in style_map:
            placemark.append(KML.styleUrl(f'#{style_map[display_group]}'))

        doc.Document.append(placemark)

    # converting to string to then write to the file
    kml_string = etree.tostring(doc, pretty_print = True).decode('utf-8')
    with open("%s.kml" %(output_file_name), "w") as file:
        file.write(kml_string)
