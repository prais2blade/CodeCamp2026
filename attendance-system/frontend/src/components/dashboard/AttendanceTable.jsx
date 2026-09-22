import { useAttendance } from "../../hooks/useAttendance";

export default function AttendanceTable({

    onSelectStudent

}) {

    const {
        data: students = [],
        isLoading
    } = useAttendance();

    return (

        <div className="bg-slate-900 rounded-xl p-5">

            <h3 className="text-xl font-semibold mb-4">

                Today's Attendance

            </h3>

            {isLoading ? (

                <div>
                    Loading...
                </div>

            ) : (

                <div className="overflow-x-auto">

                    <table className="w-full">

                        <thead>

                            <tr className="text-slate-400 border-b border-slate-800">

                                <th className="text-left py-3">
                                    Student ID
                                </th>

                                <th className="text-left py-3">
                                    Name
                                </th>

                                <th className="text-left py-3">
                                    Class
                                </th>

                                <th className="text-left py-3">
                                    Check In
                                </th>

                                <th className="text-left py-3">
                                    Status
                                </th>

                            </tr>

                        </thead>

                        <tbody>

                            {students.map((student) => (

                                <tr

                                    key={
                                        student.student_id
                                    }

                                    onClick={() =>

                                        onSelectStudent(
                                            student
                                        )

                                    }

                                    className="
                                        border-b
                                        border-slate-800
                                        cursor-pointer
                                        hover:bg-slate-800
                                        transition
                                    "

                                >

                                    <td className="py-4">

                                        {student.student_id}

                                    </td>

                                    <td>

                                        {student.name}

                                    </td>

                                    <td>

                                        {student.class_name}

                                    </td>

                                    <td>

                                        {student.check_in}

                                    </td>

                                    <td>

                                        <span className="bg-green-600 px-2 py-1 rounded text-sm">

                                            {student.status}

                                        </span>

                                    </td>

                                </tr>

                            ))}

                        </tbody>

                    </table>

                </div>

            )}

        </div>

    );

}