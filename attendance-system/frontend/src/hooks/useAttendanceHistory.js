import { useQuery } from "@tanstack/react-query";

import {

    getAttendanceHistory

} from "../api/attendanceApi";

export function useAttendanceHistory(

    studentId

) {

    return useQuery({

        queryKey: [

            "attendance-history",

            studentId

        ],

        queryFn: () =>

            getAttendanceHistory(

                studentId

            ),

        enabled: !!studentId

    });

}