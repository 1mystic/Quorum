export const members = {
  'vaikunth-heights': [
    { id: 'm-1', name: 'Meera Kulkarni', role: 'resident', unit: 'C-704', block: 'C', joined_at: '2021-03-01', status: 'active', ownership: 'owner' },
    { id: 'm-2', name: 'Suhas Patwardhan', role: 'committee_member', unit: 'D-201', block: 'D', joined_at: '2019-07-15', status: 'active', ownership: 'owner' },
    { id: 'm-3', name: 'Vikram Iyer', role: 'resident', unit: 'A-12', block: 'A', joined_at: '2023-01-10', status: 'active', ownership: 'tenant' },
    { id: 'm-4', name: 'Anjali Deshmukh', role: 'president', unit: 'B-501', block: 'B', joined_at: '2017-05-01', status: 'active', ownership: 'owner' },
    { id: 'm-5', name: 'Rahul Bhosale', role: 'treasurer', unit: 'E-303', block: 'E', joined_at: '2018-11-20', status: 'active', ownership: 'owner' },
    { id: 'm-6', name: 'Front desk security', role: 'guest', unit: '-', block: '-', joined_at: '2020-01-01', status: 'active', ownership: 'staff' },
    { id: 'm-7', name: 'Kavita Rane', role: 'auditor', unit: 'F-108', block: 'F', joined_at: '2022-09-01', status: 'pending', ownership: 'owner' }
  ],
  'aavartan-robotics': [
    { id: 'm-11', name: 'Ananya Rao', role: 'core_team', year: '3', department: 'Mechanical', joined_at: '2024-07-01', status: 'active' },
    { id: 'm-12', name: 'Karthik Menon', role: 'member', year: '2', department: 'Electronics', joined_at: '2025-07-01', status: 'active' },
    { id: 'm-13', name: 'Priya Nair', role: 'president', year: '4', department: 'Computer Science', joined_at: '2023-07-01', status: 'active' },
    { id: 'm-14', name: 'Dr. Sameer Joshi', role: 'faculty_advisor', year: '-', department: 'Mechanical', joined_at: '2021-07-01', status: 'active' },
    { id: 'm-15', name: 'Ishaan Verma', role: 'member', year: '1', department: 'Electrical', joined_at: '2026-07-01', status: 'pending' }
  ]
}

export function membersFor(slug) {
  return members[slug] || []
}
