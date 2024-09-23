from flask import Flask, render_template
from collections import defaultdict
import csv

app = Flask(__name__)

# Define regions and roles
regions = [
    'Northern Ireland', 'Wales', 'Scotland', 'London',
    'North', 'Central', 'South East', 'South and Channel Islands'
]

roles = ['Duty Manager', 'Tactical Lead']

# Read staff data from CSV file
def read_staff_from_csv():
    staff = []
    with open('staff.csv', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for idx, row in enumerate(reader):
            staff.append({
                'id': idx,  # Assign a unique ID
                'name': row['name'],
                'region': row['region'],
                'role': row['role'],
                'fte': float(row['fte']),
                # Initialize assigned shifts
                'assigned_shifts': 0,
                'assigned_shifts_weekday': 0,
                'assigned_shifts_weekend': 0,
                # Initialize expected shifts
                'expected_shifts_weekday': 0,
                'expected_shifts_weekend': 0,
                'expected_shifts': 0,
                # Initialize shift assignments
                'shift_assignments': []
            })
    return staff

staff = read_staff_from_csv()

# Shifts per day
shifts = {
    'Monday': {'Duty Manager': 2, 'Tactical Lead': 2},
    'Tuesday': {'Duty Manager': 2, 'Tactical Lead': 2},
    'Wednesday': {'Duty Manager': 2, 'Tactical Lead': 2},
    'Thursday': {'Duty Manager': 2, 'Tactical Lead': 2},
    'Friday': {'Duty Manager': 2, 'Tactical Lead': 2},
    'Saturday': {'Duty Manager': 2, 'Tactical Lead': 2},
    'Sunday': {'Duty Manager': 2, 'Tactical Lead': 2},
}

def get_role_initials(role):
    return ''.join([word[0] for word in role.split()]).upper()

def calculate_total_fte(role):
    return sum(s['fte'] for s in staff if s['role'] == role)

def calculate_staff_quotas():
    total_weeks = 52

    # Calculate total shifts per role over all weeks
    total_shifts_per_role_weekday = defaultdict(int)
    total_shifts_per_role_weekend = defaultdict(int)
    for day in shifts:
        for role in shifts[day]:
            if day in ['Saturday', 'Sunday']:
                total_shifts_per_role_weekend[role] += shifts[day][role] * total_weeks
            else:
                total_shifts_per_role_weekday[role] += shifts[day][role] * total_weeks

    # Calculate total FTE per role
    total_fte_per_role = {role: calculate_total_fte(role) for role in roles}

    # Calculate expected shifts per staff member
    for s in staff:
        s_fte = s['fte']
        role_total_shifts_weekday = total_shifts_per_role_weekday[s['role']]
        role_total_shifts_weekend = total_shifts_per_role_weekend[s['role']]
        role_total_fte = total_fte_per_role[s['role']]

        expected_shifts_weekday = (s_fte / role_total_fte) * role_total_shifts_weekday
        expected_shifts_weekend = (s_fte / role_total_fte) * role_total_shifts_weekend

        s['expected_shifts_weekday'] = int(round(expected_shifts_weekday))
        s['expected_shifts_weekend'] = int(round(expected_shifts_weekend))
        s['expected_shifts'] = s['expected_shifts_weekday'] + s['expected_shifts_weekend']

        # Reset assigned shifts and assignments
        s['assigned_shifts'] = 0
        s['assigned_shifts_weekday'] = 0
        s['assigned_shifts_weekend'] = 0
        s['shift_assignments'] = []
    return

def assign_shifts():
    total_weeks = 52
    assignments = []

    calculate_staff_quotas()

    # Prepare staff lists per role
    staff_per_role = {role: [s for s in staff if s['role'] == role] for role in roles}

    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    for week in range(1, total_weeks + 1):
        week_assignments = {'Week': week, 'Shifts': {}}
        for day in day_order:
            is_weekend = day in ['Saturday', 'Sunday']
            shift_assignments = {}
            regions_on_shift = set()  # Keep track of regions assigned on this day
            for role in shifts[day]:
                required_shifts = shifts[day][role]
                shift_assignments[role] = [None] * required_shifts  # Initialize shifts

                assigned_staff_for_day_role = set()  # To prevent assigning the same staff to multiple shifts in the same day and role

                # Assign staff for each required shift
                for shift_number in range(required_shifts):
                    attempts = 0
                    assigned = False
                    while not assigned and attempts < 200:
                        attempts += 1

                        # Candidates are staff who have not exceeded their expected shifts, not assigned today for this role, and from regions not already on shift
                        if is_weekend:
                            candidates = [s for s in staff_per_role[role]
                                        if s['assigned_shifts_weekend'] < s['expected_shifts_weekend']
                                        and s['id'] not in assigned_staff_for_day_role
                                        and s['region'] not in regions_on_shift]
                        else:
                            candidates = [s for s in staff_per_role[role]
                                        if s['assigned_shifts_weekday'] < s['expected_shifts_weekday']
                                        and s['id'] not in assigned_staff_for_day_role
                                        and s['region'] not in regions_on_shift]

                        if not candidates:
                            # Relax region constraint
                            if is_weekend:
                                candidates = [s for s in staff_per_role[role]
                                            if s['assigned_shifts_weekend'] < s['expected_shifts_weekend']
                                            and s['id'] not in assigned_staff_for_day_role]
                            else:
                                candidates = [s for s in staff_per_role[role]
                                            if s['assigned_shifts_weekday'] < s['expected_shifts_weekday']
                                            and s['id'] not in assigned_staff_for_day_role]

                        if not candidates:
                            # Consider all staff not assigned today for this role
                            candidates = [s for s in staff_per_role[role]
                                        if s['id'] not in assigned_staff_for_day_role]

                        # Sort candidates by the fewest over-assigned shifts and assigned shifts per FTE
                        if is_weekend:
                            candidates.sort(key=lambda x: (
                                x['assigned_shifts_weekend'] - x['expected_shifts_weekend'],
                                x['assigned_shifts']/x['fte']))
                        else:
                            candidates.sort(key=lambda x: (
                                x['assigned_shifts_weekday'] - x['expected_shifts_weekday'],
                                x['assigned_shifts']/x['fte']))

                        if candidates:
                            s = candidates[0]
                            s['assigned_shifts'] += 1
                            if is_weekend:
                                s['assigned_shifts_weekend'] += 1
                            else:
                                s['assigned_shifts_weekday'] += 1

                            # Record the shift assignment with shift number
                            s['shift_assignments'].append({
                                'Week': week,
                                'Day': day,
                                'Role': role,
                                'Shift Number': shift_number + 1
                            })

                            shift_assignments[role][shift_number] = s
                            assigned_staff_for_day_role.add(s['id'])
                            regions_on_shift.add(s['region'])
                            assigned = True
                        else:
                            # If no staff can be assigned, leave shift as None
                            assigned = True

            # **Assign shifts for the current day**
            week_assignments['Shifts'][day] = shift_assignments  # **Corrected Line**

        assignments.append(week_assignments)
    return assignments

assignments = assign_shifts()  # Generate assignments once to use in all views

# Route for the individual staff view
@app.route('/individual_shifts')
def individual_shifts_view():
    return render_template('individual_shifts.html', staff=staff)

@app.route('/staff_list')
def staff_list_view():
    return render_template('staff_list.html', staff=staff)

@app.route('/patterns_combined')
def patterns_combined_view():
    # Prepare data per week
    patterns = []
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    for week_data in assignments:
        week = week_data['Week']
        week_pattern = {'Week': week}
        for day in day_names:
            for role in ['Duty Manager', 'Tactical Lead']:
                shifts = week_data['Shifts'][day][role]
                for idx in range(2):
                    staff_member = shifts[idx] if idx < len(shifts) and shifts[idx] else None
                    role_initials = get_role_initials(role)
                    key = f"{day} {role_initials} {idx + 1}"
                    if staff_member:
                        week_pattern[key] = f"{staff_member['name']}"
                    else:
                        week_pattern[key] = '-'
        patterns.append(week_pattern)
    return render_template('patterns_combined.html', patterns=patterns)

@app.route('/patterns_by_day')
def patterns_by_day_view():
    """
    Prepare data to display shifts with columns:
    Week | Day of Week | DM 1 | DM 2 | TL 1 | TL 2
    """
    patterns = []
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    for week_data in assignments:
        week = week_data['Week']
        for day in day_names:
            shift_info = week_data['Shifts'][day]
            # Initialize dictionary for the current row
            pattern = {
                'Week': week,
                'Day': day,
                'DM 1': '-',
                'DM 2': '-',
                'TL 1': '-',
                'TL 2': '-'
            }
            
            # Assign Duty Managers
            dm_shifts = shift_info.get('Duty Manager', [])
            for idx in range(2):
                key = f'DM {idx + 1}'
                if idx < len(dm_shifts) and dm_shifts[idx]:
                    pattern[key] = dm_shifts[idx]['name']
                else:
                    pattern[key] = '-'
            
            # Assign Tactical Leads
            tl_shifts = shift_info.get('Tactical Lead', [])
            for idx in range(2):
                key = f'TL {idx + 1}'
                if idx < len(tl_shifts) and tl_shifts[idx]:
                    pattern[key] = tl_shifts[idx]['name']
                else:
                    pattern[key] = '-'
            
            patterns.append(pattern)
    
    return render_template('patterns_by_day.html', patterns=patterns)

@app.route('/patterns_combined_with_regions')
def patterns_combined_with_regions_view():
    # Prepare data per week
    patterns = []
    day_names = ['1', '2', '3', '4', '5', '6', '7']
    for week_data in assignments:
        week = week_data['Week']
        week_pattern = {'Week': week}
        for day in day_names:
            regions_on_shift = set()
            for role in ['Duty Manager', 'Tactical Lead']:
                shifts = week_data['Shifts'][day][role]
                for idx in range(2):
                    staff_member = shifts[idx] if idx < len(shifts) and shifts[idx] else None
                    role_initials = get_role_initials(role)
                    key = f"{day} {role_initials} {idx + 1}"
                    if staff_member:
                        week_pattern[key] = f"{staff_member['name']} ({staff_member['region']})"
                        regions_on_shift.add(staff_member['region'])
                    else:
                        week_pattern[key] = '-'
            # Add the count of different regions on shift for the day
            week_pattern[f"{day} Regions"] = len(regions_on_shift)
        patterns.append(week_pattern)
    return render_template('patterns_combined_with_regions.html', patterns=patterns)

# Existing routes
@app.route('/')
def index():
    return render_template('shifts.html', assignments=assignments, shifts=shifts)

@app.route('/staff')
def staff_view():
    return render_template('staff.html', staff=staff)

# Route for weekly calendar view
@app.route('/calendar')
def calendar_view():
    # Prepare data per week
    calendar_data = {}
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    for week in range(1, 53):
        week_data = {day: {'Duty Manager': [], 'Tactical Lead': []} for day in day_names}
        calendar_data[week] = week_data

    for assignment in assignments:
        week = assignment['Week']
        for day, roles in assignment['Shifts'].items():
            for role, staff_list in roles.items():
                for staff_member in staff_list:
                    if staff_member:
                        calendar_data[week][day][role].append({
                            'name': staff_member['name'],
                            'region': staff_member['region']
                        })
    return render_template('calendar.html', calendar_data=calendar_data)

if __name__ == '__main__':
    app.run(debug=True)