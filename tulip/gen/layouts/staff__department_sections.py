"""
staff.department_sections: Section rows name the department.
"""
from gen import b_people as P

ID = 'staff.department_sections'
TARGET = 'staff'


def build(ctx, plan):
    return P.staff(ctx, plan, dept_sections=True)
