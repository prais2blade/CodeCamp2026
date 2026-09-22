import { useQuery }
from "@tanstack/react-query";

import {
    getTodayAttendance
}
from "../api/attendanceApi";

export function useAttendance() {

    return useQuery({

        queryKey: [
            "attendance"
        ],

        queryFn:
            getTodayAttendance,

    });

}