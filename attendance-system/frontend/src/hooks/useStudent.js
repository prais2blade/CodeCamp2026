import { useQuery } from "@tanstack/react-query";

import { getStudentDetail } from "../api/studentApi";

export function useStudent(studentId) {

    return useQuery({

        queryKey: [
            "student",
            studentId
        ],

        queryFn: () =>
            getStudentDetail(
                studentId
            ),

        enabled: !!studentId,

    });

}