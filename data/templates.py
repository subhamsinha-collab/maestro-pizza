"""Generate sample CSV templates for user downloads."""
import pandas as pd

TEMPLATES = {
    "cars_restriction": {
        "columns": ["Branch", "Hr", "1", "2", "3", "4", "5", "6", "7"],
        "sample_data": [["Aarid 2",0,0,0,0,0,0,0,0],["Aarid 2",12,2,2,2,2,2,2,2],["Aarid 2",18,2,2,2,2,3,3,2],["AR Rimal",12,2,2,2,2,2,2,2],["AR Rimal",18,3,3,3,3,3,3,3]],
    },
    "restricted_branches": {
        "columns": ["Branch"],
        "sample_data": [["Branch_Name_1"],["Branch_Name_2"],["Branch_Name_3"]],
    },
    "employee_restriction": {
        "columns": ["Branch","Max team size","Coming time","Going time cap","Maxm hours gap between days","Weekoff day","Saudi/Expat"],
        "sample_data": [["Aarid 2",1,11,2,2,"","Saudi"],["Yasmin",2,11,2,2,"","Saudi"],["Yasmin",2,9,3,3,"Friday","Expat"],["Narjis",1,11,2,2,"","Saudi"]],
    },
    "mc_restriction": {
        "columns": ["Branch","Max team size"],
        "sample_data": [["Aarid 2",3],["AR Rimal",2],["Narjis",3],["Cortoba",1]],
    },
    "3p_preference": {
        "columns": ["Branch","MC Preferred?","1st Priority","2nd Priority","3rd Priority"],
        "sample_data": [["Aarid 2","Yes","C","C","Y"],["AR Rimal","Yes","H","C","Y"],["Narjis","No","C","H","Y"]],
    },
}

def generate_template(template_name):
    t = TEMPLATES.get(template_name)
    if not t:
        raise ValueError(f"Unknown template: {template_name}")
    df = pd.DataFrame(t["sample_data"], columns=t["columns"])
    return df.to_csv(index=False).encode("utf-8")
