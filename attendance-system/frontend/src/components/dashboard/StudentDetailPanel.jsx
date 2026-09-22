import { useStudent } from "../../hooks/useStudent";
import { useAttendanceHistory } from "../../hooks/useAttendanceHistory";

export default function StudentDetailPanel({

    studentId

}) {

    const {

        data: student,

        isLoading

    } = useStudent(studentId);

    const {

        data: history = [],

        isLoading: historyLoading

    } = useAttendanceHistory(studentId);

    if (!studentId) {

        return (

            <div className="bg-slate-900 rounded-xl p-6 min-h-150">

                <h3 className="text-xl font-semibold mb-4">

                    Student Details

                </h3>

                <p className="text-slate-400">

                    Select a student from the attendance table.

                </p>

            </div>

        );

    }

    if (isLoading) {

        return (

            <div className="bg-slate-900 rounded-xl p-6 min-h-150">

                Loading student details...

            </div>

        );

    }

    return (

        <div className="bg-slate-900 rounded-xl p-6 min-h-150">

            <h3 className="text-xl font-semibold mb-4">

                Student Details

            </h3>

            {/* Student Photo */}

            <div className="flex justify-center mb-6">

                {student?.photo ? (

                    <img

                        src={student.photo}

                        alt={student.first_name}

                        className="
                            h-28
                            w-28
                            rounded-full
                            object-cover
                            border-2
                            border-slate-700
                        "

                    />

                ) : (

                    <div className="h-28 w-28 rounded-full bg-slate-800">

                    </div>

                )}

            </div>

            {/* Student Information */}

            <div className="space-y-3">

                <div>

                    <p className="text-slate-400">

                        Name

                    </p>

                    <p>

                        {student?.first_name} {student?.last_name}

                    </p>

                </div>

                <div>

                    <p className="text-slate-400">

                        Student ID

                    </p>

                    <p>

                        {student?.student_id}

                    </p>

                </div>

                <div>

                    <p className="text-slate-400">

                        Class

                    </p>

                    <p>

                        {student?.class_name}

                    </p>

                </div>

                <div>

                    <p className="text-slate-400">

                        Gender

                    </p>

                    <p>

                        {student?.gender}

                    </p>

                </div>

            </div>

            <hr className="border-slate-700 my-4" />

            {/* Parent Information */}

            <h4 className="font-semibold mb-3">

                Parent Information

            </h4>

            <div className="space-y-3">

                <div>

                    <p className="text-slate-400">

                        Parent Name

                    </p>

                    <p>

                        {student?.parent?.name || "N/A"}

                    </p>

                </div>

                <div>

                    <p className="text-slate-400">

                        Phone

                    </p>

                    <p>

                        {student?.parent?.phone || "N/A"}

                    </p>

                </div>

                <div>

                    <p className="text-slate-400">

                        Email

                    </p>

                    <p>

                        {student?.parent?.email || "N/A"}

                    </p>

                </div>

                <div>

                    <p className="text-slate-400">

                        WhatsApp

                    </p>

                    <p>

                        {student?.parent?.whatsapp || "N/A"}

                    </p>

                </div>

            </div>

            <hr className="border-slate-700 my-4" />

            {/* Attendance History */}

            <h4 className="font-semibold mb-3">

                Attendance History

            </h4>

            {historyLoading ? (

                <p className="text-slate-400">

                    Loading attendance history...

                </p>

            ) : history.length === 0 ? (

                <p className="text-slate-400">

                    No attendance history found.

                </p>

            ) : (

                <div className="space-y-2">

                    {history.map((record, index) => (

                        <div

                            key={index}

                            className="
                                bg-slate-800
                                rounded-lg
                                p-3
                            "

                        >

                            <div className="font-medium">

                                {record.date}

                            </div>

                            <div className="text-sm text-slate-300">

                                Check In:
                                {" "}
                                {record.check_in}

                            </div>

                            <div className="text-sm text-slate-300">

                                Check Out:
                                {" "}
                                {record.check_out}

                            </div>

                        </div>

                    ))}

                </div>

            )}

        </div>

    );

}