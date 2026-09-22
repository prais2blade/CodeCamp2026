import apiClient from "./apiClient";

export const getTodayAttendance =
    async () => {

        const response =
            await apiClient.get(
                "/attendance/today/"
            );

        return response.data;

    };

export const getAttendanceHistory = async (

    studentId

) => {

    const response = await apiClient.get(

        `/attendance/history/${studentId}/`

    );

    return response.data;

};