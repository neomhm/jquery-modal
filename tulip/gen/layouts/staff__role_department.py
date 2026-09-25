"""
staff.role_department: Role and department columns.
"""
from gen import b_people as P

ID = 'staff.role_department'
TARGET = 'staff'


def build(ctx, plan):
    return P.staff(ctx, plan, role_department=True)
