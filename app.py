from flask import Flask, render_template
from collections import defaultdict
import random

app = Flask(__name__)

# Define regions
regions = [
    'Northern Ireland', 'Wales', 'Scotland', 'London',
    'North', 'Central', 'South East', 'South and Channel Islands'
]

# Roles
roles = ['Duty Manager', 'Tactical Lead']

# Generate sample staff data
def generate_staff():
    staff = []
    names = [
        'Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank', 'Grace', 'Heidi',
        'Ivan', 'Judy', 'Karl', 'Liam', 'Mallory', 'Niaj', 'Olivia', 'Peggy',
        'Quentin', 'Ruth', 'Sybil', 'Trent', 'Uma', 'Victor', 'Walter', 'Xena',
        'Yvonne', 'Zach', 'Anna', 'Brian', 'Catherine', 'David', 'Ella', 'Fiona',
        'George', 'Hannah', 'Ian', 'Julia', 'Kevin', 'Laura'
    ]

    fte_options = [1.0, 0.8, 0.6]
    for name in names[:38]:
        staff.append({
            'name': name,
            'region': random.choice(regions),
            'role': random.choice(roles),
            'fte': random.choice(fte_options),
            'assigned_shifts': 0,  # Total assigned shifts
            'weeknight_shifts': 0,
            'weekend_shifts': 0,
            'expected_weeknight_shifts': 0,
            'expected_weekend_shifts': 0,
            'shift_assignments': []  # List of shifts assigned to the staff member
        })
    return staff

staff = generate_staff()

# Shifts per week
shifts = {
    'Weeknight': {
        'Duty Manager': 2,
        'Tactical Lead': 2
    },
    'Weekend': {
        'Duty Manager': 2,
        'Tactical Lead': 2
    }
}

def calculate_total_fte(role):
    return sum(s['fte'] for s in staff if s['role'] == role)

def calculate_staff_quotas():
    # Total weeks
    total_weeks = 52

    # Calculate total shifts per role and shift time over all weeks
    total_shifts = {}
    for shift_time in shifts:
        for role in shifts[shift_time]:
            total_shifts[(shift_time, role)] = shifts[shift_time][role] * total_weeks

    # Calculate total FTE per role
    total_fte_per_role = {role: calculate_total_fte(role) for role in roles}

    # Calculate expected shifts per staff member for each shift time
    for s in staff:
        for shift_time in shifts:
            role_total_shifts = total_shifts[(shift_time, s['role'])]
            s_fte = s['fte']
            role_total_fte = total_fte_per_role[s['role']]

            expected_shifts = (s_fte / role_total_fte) * role_total_shifts
            expected_shifts = int(round(expected_shifts))

            if shift_time == 'Weeknight':
                s['expected_weeknight_shifts'] = expected_shifts
            else:
                s['expected_weekend_shifts'] = expected_shifts

        # Reset assigned shifts
        s['assigned_shifts'] = 0
        s['weeknight_shifts'] = 0
        s['weekend_shifts'] = 0
        s['shift_assignments'] = []
    return

def assign_shifts():
    total_weeks = 52
    assignments = []

    calculate_staff_quotas()

    # Prepare staff lists per role
    staff_per_role = {role: [s for s in staff if s['role'] == role] for role in roles}

    for week in range(1, total_weeks + 1):
        week_assignments = {'Week': week, 'Shifts': {}}
        for shift_time in shifts:
            shift_assignments = {'Duty Manager': [], 'Tactical Lead': []}
            regions_on_shift = set()
            for role in shifts[shift_time]:
                required_shifts = shifts[shift_time][role]

                # Candidates are staff who have not exceeded their expected shifts
                candidates = [s for s in staff_per_role[role]]

                assigned = []
                attempts = 0  # To prevent infinite loops
                while len(assigned) < required_shifts and attempts < 200:
                    attempts += 1
                    # Filter candidates who have not exceeded their expected shifts
                    if shift_time == 'Weeknight':
                        candidates_available = [s for s in candidates if s['weeknight_shifts'] < s['expected_weeknight_shifts']]
                    else:
                        candidates_available = [s for s in candidates if s['weekend_shifts'] < s['expected_weekend_shifts']]

                    if not candidates_available:
                        # If no candidates available, consider all staff (even those who have exceeded expected shifts)
                        candidates_available = candidates

                    # Exclude staff from regions already assigned
                    candidates_available = [s for s in candidates_available if s['region'] not in regions_on_shift]

                    if not candidates_available:
                        # If still no candidates, we must relax the region constraint
                        # Consider staff from the same region but have the least over-assigned shifts
                        candidates_available = [s for s in candidates]

                        # Exclude staff already assigned in this shift
                        candidates_available = [s for s in candidates_available if s not in assigned]

                    # Sort candidates by the fewest over-assigned shifts and FTE
                    if shift_time == 'Weeknight':
                        candidates_available.sort(key=lambda x: (x['weeknight_shifts'] - x['expected_weeknight_shifts'], x['assigned_shifts']/x['fte']))
                    else:
                        candidates_available.sort(key=lambda x: (x['weekend_shifts'] - x['expected_weekend_shifts'], x['assigned_shifts']/x['fte']))

                    # Assign the first candidate
                    for s in candidates_available:
                        if s not in assigned:
                            assigned.append(s)
                            regions_on_shift.add(s['region'])
                            s['assigned_shifts'] += 1
                            if shift_time == 'Weeknight':
                                s['weeknight_shifts'] += 1
                            else:
                                s['weekend_shifts'] += 1

                            # Record the shift assignment with day mapping
                            if shift_time == 'Weeknight':
                                days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday']
                            else:
                                days = ['Friday', 'Saturday', 'Sunday']

                            for day in days:
                                s['shift_assignments'].append({
                                    'Week': week,
                                    'Day': day,
                                    'Shift Time': shift_time,
                                    'Role': role
                                })

                            shift_assignments[role].append(s)
                            break
                    else:
                        break  # Break if no one can be assigned
            week_assignments['Shifts'][shift_time] = shift_assignments
        assignments.append(week_assignments)
    return assignments

assignments = assign_shifts()  # Generate assignments once to use in all views

# Route for the shift schedule view
@app.route('/schedule')
def schedule_view():
    return render_template('schedule.html', assignments=assignments, shifts=shifts)

# Route for the manager's view
@app.route('/region_shifts')
def region_shifts_view():
    # Prepare data: flatten shifts for sorting
    region_shifts = []
    day_order = {'Monday': 1, 'Tuesday': 2, 'Wednesday': 3, 'Thursday': 4,
                 'Friday': 5, 'Saturday': 6, 'Sunday': 7}
    for s in staff:
        for shift in s['shift_assignments']:
            region_shifts.append({
                'Region': s['region'],
                'Week': shift['Week'],
                'Day': shift['Day'],
                'DayOrder': day_order[shift['Day']],
                'Shift Time': shift['Shift Time'],
                'Staff': s['name'],
                'Role': s['role']
            })
    # Sort the shifts by Week and DayOrder
    region_shifts.sort(key=lambda x: (x['Week'], x['DayOrder']))
    return render_template('region_shifts.html', region_shifts=region_shifts)

# Route for the individual staff view
@app.route('/individual_shifts')
def individual_shifts_view():
    return render_template('individual_shifts.html', staff=staff)

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
        for shift_time, roles in assignment['Shifts'].items():
            if shift_time == 'Weeknight':
                days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday']
            else:
                days = ['Friday', 'Saturday', 'Sunday']
            for role, staff_list in roles.items():
                for staff_member in staff_list:
                    for day in days:
                        calendar_data[week][day][role].append({
                            'name': staff_member['name'],
                            'region': staff_member['region']
                        })
    return render_template('calendar.html', calendar_data=calendar_data)

if __name__ == '__main__':
    app.run(debug=True)